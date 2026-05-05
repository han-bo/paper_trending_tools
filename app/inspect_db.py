"""在终端查看 SQLite 中已抓取的 GitHub / arXiv / digest（无需 sqlite3 客户端）。"""

from __future__ import annotations

import sys
from sqlalchemy import func, select

from app.config import settings
from app.db.models import ArxivPaper, DailyDigest, GitHubProject
from app.db.session import get_session, init_db


def _snip(text: str | None, max_len: int = 160) -> str:
    if not text:
        return "（无）"
    one = " ".join(text.split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def inspect_database(*, limit: int = 20, digest_limit: int = 5) -> None:
    init_db()
    session = get_session()
    try:
        url = settings.database_url
        print("=== 数据库概览 ===")
        print(f"DATABASE_URL: {url}")
        print()

        n_gh = session.scalar(select(func.count()).select_from(GitHubProject)) or 0
        n_ax = session.scalar(select(func.count()).select_from(ArxivPaper)) or 0
        n_dd = session.scalar(select(func.count()).select_from(DailyDigest)) or 0
        print(f"github_projects: {n_gh} 条")
        print(f"arxiv_papers:    {n_ax} 条")
        print(f"daily_digest:    {n_dd} 条")
        print()

        gh_rows = session.scalars(
            select(GitHubProject).order_by(GitHubProject.id.desc()).limit(limit)
        ).all()
        print(f"--- GitHub 最近 {len(gh_rows)} 条（id 从新到旧）---")
        for r in gh_rows:
            ts = r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else ""
            print(
                f"[{r.id}] {r.repo_name}  ★{r.stars}  分{r.score:.1f}  "
                f"关注:{r.worth_follow}  {ts}"
            )
            print(f"     {r.repo_url}")
            print(f"     摘要: {_snip(r.ai_summary, 200)}")
            print()

        ax_rows = session.scalars(
            select(ArxivPaper).order_by(ArxivPaper.id.desc()).limit(limit)
        ).all()
        print(f"--- arXiv 最近 {len(ax_rows)} 条 ---")
        for r in ax_rows:
            ts = r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else ""
            title = _snip(r.title, 100)
            print(f"[{r.id}] {title}  分{r.score:.1f}  {ts}")
            print(f"     {r.paper_url}")
            print(f"     摘要: {_snip(r.ai_summary, 200)}")
            print()

        dd_rows = session.scalars(
            select(DailyDigest).order_by(DailyDigest.id.desc()).limit(digest_limit)
        ).all()
        print(f"--- 每日摘要最近 {len(dd_rows)} 条 ---")
        for r in dd_rows:
            ts = r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else ""
            print(f"[{r.id}] date={r.date}  status={r.sent_status}  {ts}")
            print(_snip(r.content, 2000))
            print()
    finally:
        session.close()


def main_argv(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(description="查看本地库中抓取结果")
    p.add_argument("--limit", type=int, default=20, help="GitHub / arXiv 各显示最近几条（默认 20）")
    p.add_argument("--digest-limit", type=int, default=5, help="daily_digest 显示几条（默认 5）")
    args = p.parse_args(argv)
    if args.limit < 1 or args.digest_limit < 1:
        print("limit 须 >= 1", file=sys.stderr)
        sys.exit(1)
    inspect_database(limit=args.limit, digest_limit=args.digest_limit)


if __name__ == "__main__":
    main_argv()
