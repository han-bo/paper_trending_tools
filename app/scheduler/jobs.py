from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import httpx
from loguru import logger
from sqlalchemy import func, select

from app.config import settings
from app.crawler.arxiv import fetch_arxiv_entries
from app.crawler.github import search_hot_repositories
from app.db.models import ArxivPaper, DailyDigest, GitHubProject
from app.db.session import get_session, init_db
from app.llm.prompt_builder import (
    build_github_prompt,
    build_paper_prompt,
    parse_final_score_1_to_10,
)
from app.llm.volcengine_client import chat_completions
from app.notifier.email_notify import email_notify_configured, send_digest_email
from app.notifier.telegram_bot import send_digest
from app.ranking.arxiv_score import (
    combine_arxiv_scores,
    compute_engineering_score as arxiv_engineering,
    worth_follow_from_ai_rating as arxiv_worth,
)
from app.ranking.github_score import (
    combine_github_scores,
    compute_engineering_score as gh_engineering,
    worth_follow_from_ai_rating as gh_worth,
)


def _today_tag() -> str:
    tz = ZoneInfo(settings.scheduler_timezone)
    return datetime.now(tz=tz).date().isoformat()


def _max_id(session, model) -> int:
    v = session.scalar(select(func.max(model.id)))
    return int(v or 0)


def _sleep_between_llm_calls() -> None:
    """降低连续请求触发方舟限频的概率；VOLCENGINE_LLM_INTERVAL_SECONDS=0 可关闭。"""
    sec = settings.volcengine_llm_interval_seconds
    if sec > 0:
        time.sleep(sec)


def run_daily_pipeline() -> None:
    init_db()
    session = get_session()
    digest_date = _today_tag()
    try:
        last_gh = _max_id(session, GitHubProject)
        last_ax = _max_id(session, ArxivPaper)

        logger.info("抓取 GitHub …")
        repos = search_hot_repositories()
        for r in repos:
            prev = session.scalar(
                select(GitHubProject.stars)
                .where(GitHubProject.repo_name == r["repo_name"])
                .order_by(GitHubProject.id.desc())
                .limit(1)
            )
            stars_growth = int(r["stars"] - prev) if prev is not None else 0
            payload = {**r, "stars_growth": stars_growth}
            eng = gh_engineering(payload)
            session.add(
                GitHubProject(
                    repo_name=r["repo_name"],
                    repo_url=r["repo_url"],
                    stars=int(r["stars"]),
                    stars_growth=stars_growth,
                    contributors=int(r["contributors"]),
                    last_commit_at=r.get("last_commit_at"),
                    issue_count=int(r["issue_count"]),
                    release_count=int(r["release_count"]),
                    language=r.get("language"),
                    topic=r.get("topic"),
                    raw_readme=r.get("raw_readme"),
                    score=float(eng),
                    ai_summary=None,
                    worth_follow=False,
                )
            )

        logger.info("抓取 arXiv …")
        papers = fetch_arxiv_entries()
        for p in papers:
            eng = arxiv_engineering(p)
            session.add(
                ArxivPaper(
                    title=p["title"],
                    authors=p.get("authors"),
                    abstract=p.get("abstract"),
                    paper_url=p["paper_url"],
                    pdf_url=p.get("pdf_url"),
                    category=p.get("category"),
                    published_at=p.get("published_at"),
                    github_repo_url=p.get("github_repo_url"),
                    score=float(eng),
                    ai_summary=None,
                    worth_follow=False,
                )
            )
        session.commit()

        new_github = session.scalars(
            select(GitHubProject).where(GitHubProject.id > last_gh).order_by(GitHubProject.score.desc())
        ).all()
        new_arxiv = session.scalars(
            select(ArxivPaper).where(ArxivPaper.id > last_ax).order_by(ArxivPaper.score.desc())
        ).all()

        llm_ready = bool(settings.volcengine_api_key and settings.volcengine_model)

        if llm_ready:
            logger.info("LLM 分析 GitHub Top {} …", settings.llm_analyze_github_top)
            for row in new_github[: settings.llm_analyze_github_top]:
                desc_snip = ""
                if row.raw_readme:
                    desc_snip = row.raw_readme.strip().split("\n\n", 1)[0][:800]
                recent_activity = (
                    f"Stars 增长：{row.stars_growth}；Issue：{row.issue_count}；Release：{row.release_count}"
                )
                if row.last_commit_at:
                    recent_activity += f"；最近提交：{row.last_commit_at.date().isoformat()}"
                prompt = build_github_prompt(
                    repo_name=row.repo_name,
                    description=desc_snip or "（无单独描述字段，详见 README）",
                    readme=row.raw_readme or "",
                    stars=row.stars,
                    contributors=row.contributors,
                    recent_activity=recent_activity,
                )
                try:
                    text = chat_completions([{"role": "user", "content": prompt}])
                except httpx.TimeoutException as e:
                    logger.warning(
                        "GitHub LLM 超时（read {:.0f}s）{}: {}",
                        settings.volcengine_read_timeout,
                        row.repo_name,
                        e,
                    )
                    continue
                except Exception as e:
                    logger.exception("GitHub LLM 失败 {}: {}", row.repo_name, e)
                    continue
                rating = parse_final_score_1_to_10(text)
                eng = gh_engineering(
                    {
                        "stars": row.stars,
                        "stars_growth": row.stars_growth,
                        "contributors": row.contributors,
                        "release_count": row.release_count,
                        "issue_count": row.issue_count,
                        "last_commit_at": row.last_commit_at,
                    }
                )
                row.ai_summary = text
                row.score = combine_github_scores(eng, rating)
                row.worth_follow = gh_worth(rating)
                session.add(row)
                _sleep_between_llm_calls()

            logger.info("LLM 分析 arXiv Top {} …", settings.llm_analyze_arxiv_top)
            for row in new_arxiv[: settings.llm_analyze_arxiv_top]:
                prompt = build_paper_prompt(
                    title=row.title,
                    abstract=row.abstract or "",
                    authors=row.authors or "",
                    category=row.category or "",
                    github_repo=row.github_repo_url or "",
                )
                try:
                    text = chat_completions([{"role": "user", "content": prompt}])
                except httpx.TimeoutException as e:
                    logger.warning(
                        "arXiv LLM 超时（read {:.0f}s）{}: {}",
                        settings.volcengine_read_timeout,
                        row.title[:80],
                        e,
                    )
                    continue
                except Exception as e:
                    logger.exception("arXiv LLM 失败 {}: {}", row.title[:80], e)
                    continue
                rating = parse_final_score_1_to_10(text)
                eng = arxiv_engineering(
                    {
                        "abstract": row.abstract,
                        "github_repo_url": row.github_repo_url,
                        "category": row.category,
                        "authors": row.authors,
                    }
                )
                row.ai_summary = text
                row.score = combine_arxiv_scores(eng, rating)
                row.worth_follow = arxiv_worth(rating)
                session.add(row)
                _sleep_between_llm_calls()
            session.commit()
        else:
            logger.warning("跳过 LLM：未配置 VOLCENGINE_API_KEY / VOLCENGINE_MODEL")

        new_github = session.scalars(
            select(GitHubProject).where(GitHubProject.id > last_gh).order_by(GitHubProject.score.desc())
        ).all()
        new_arxiv = session.scalars(
            select(ArxivPaper).where(ArxivPaper.id > last_ax).order_by(ArxivPaper.score.desc())
        ).all()

        def _row_dict(obj) -> dict:
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

        gh_df = pd.DataFrame([_row_dict(g) for g in new_github])
        if not gh_df.empty:
            gh_df = gh_df.sort_values("score", ascending=False)
        ax_df = pd.DataFrame([a.__dict__ for a in new_arxiv])
        if not ax_df.empty:
            ax_df = ax_df.sort_values("score", ascending=False)

        def _snip_reason(ai_summary: object, *, max_chars: int = 260) -> str:
            if not isinstance(ai_summary, str) or not ai_summary.strip():
                return ""
            raw_lines = [ln.rstrip() for ln in ai_summary.strip().splitlines()]
            # 常见 LLM 输出会先给 Markdown 标题（例如 "### 1. 是否值得持续关注"），
            # digest 更关心后面的解释正文：跳过开头标题与紧随的空行，取“第一段”（到空行为止）。
            i = 0
            while i < len(raw_lines) and not raw_lines[i].strip():
                i += 1
            while i < len(raw_lines) and raw_lines[i].lstrip().startswith("#"):
                i += 1
                while i < len(raw_lines) and not raw_lines[i].strip():
                    i += 1

            para: list[str] = []
            while i < len(raw_lines):
                ln = raw_lines[i].strip()
                if not ln:
                    break
                para.append(ln)
                i += 1

            if not para:
                # 只有标题或格式异常时，退回用第一条非空行
                for ln in raw_lines:
                    if ln.strip():
                        para = [ln.strip()]
                        break

            text = " ".join(para).strip()
            if len(text) > max_chars:
                text = text[:max_chars].rstrip() + "…"
            return text

        digest_lines: list[str] = ["【今日值得关注】", "", "GitHub Top {}".format(settings.digest_github_top_n), ""]
        top_gh = gh_df.head(settings.digest_github_top_n) if not gh_df.empty else gh_df
        idx = 1
        for _, r in top_gh.iterrows():
            reason = _snip_reason(r.get("ai_summary"))
            digest_lines.append(f"{idx}. {r['repo_name']}")
            digest_lines.append(f"原因：{reason or '（规则层排序，尚未生成摘要）'}")
            digest_lines.append(f"评分：{float(r['score']):.1f}")
            digest_lines.append(f"链接：{r['repo_url']}")
            digest_lines.append("")
            idx += 1

        digest_lines.append("arXiv Top {}".format(settings.digest_arxiv_top_n))
        digest_lines.append("")
        top_ax = ax_df.head(settings.digest_arxiv_top_n) if not ax_df.empty else ax_df
        idx = 1
        for _, r in top_ax.iterrows():
            reason = _snip_reason(r.get("ai_summary"))
            digest_lines.append(f"{idx}. {r['title']}")
            digest_lines.append(f"原因：{reason or '（规则层排序，尚未生成摘要）'}")
            digest_lines.append(f"评分：{float(r['score']):.1f}")
            digest_lines.append(f"链接：{r['paper_url']}")
            digest_lines.append("")
            idx += 1

        pick = "（暂无）"
        if not gh_df.empty:
            pick = str(gh_df.iloc[0]["repo_name"])
        elif not ax_df.empty:
            pick = str(ax_df.iloc[0]["title"])
        digest_lines.append("建议：")
        digest_lines.append(f"今天最值得深入研究的是：{pick}")

        content = "\n".join(digest_lines).strip()
        status_parts: list[str] = []

        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                send_digest(content)
                status_parts.append("telegram:sent")
            except Exception as e:
                logger.exception("Telegram 推送失败: {}", e)
                status_parts.append(f"telegram:error:{e}")
        else:
            logger.warning("跳过 Telegram：未配置 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

        if email_notify_configured():
            try:
                send_digest_email(content)
                status_parts.append("email:sent")
            except Exception as e:
                logger.exception("邮件发送失败: {}", e)
                status_parts.append(f"email:error:{e}")
        else:
            logger.warning(
                "跳过邮件：未配置完整的 Zoho Mail API（见 .env.example 中 ZOHO_*）"
                "或未配置 DIGEST_EMAIL_TO"
            )

        if not status_parts:
            sent_status = "skipped"
        else:
            sent_status = ";".join(status_parts)

        session.add(
            DailyDigest(
                date=digest_date,
                content=content,
                sent_status=sent_status,
            )
        )
        session.commit()
        logger.info("每日流程完成，digest 日期={} 状态={}", digest_date, sent_status)
    finally:
        session.close()


def setup_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched = BlockingScheduler(timezone=ZoneInfo(settings.scheduler_timezone))
    sched.add_job(
        run_daily_pipeline,
        CronTrigger(
            hour=settings.scheduler_cron_hour,
            minute=settings.scheduler_cron_minute,
        ),
        id="daily_research_digest",
        replace_existing=True,
    )
    return sched
