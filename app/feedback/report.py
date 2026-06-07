from __future__ import annotations

import html
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ArxivPaper, GitHubProject, UserFeedback
from app.feedback.penalty import penalty_for_down_count
from app.notifier.email_notify import email_notify_configured, send_report_email

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _confirm_html(*, signal: str, item_type: str, item_key: str, digest_date: str) -> str:
    tpl_path = _STATIC_DIR / "confirm.html"
    tpl = tpl_path.read_text(encoding="utf-8")
    label = "👍 值得" if signal == "up" else "👎 不满意"
    type_label = "GitHub" if item_type == "github" else "arXiv"
    return (
        tpl.replace("{{LABEL}}", html.escape(label))
        .replace("{{TYPE}}", html.escape(type_label))
        .replace("{{ITEM_KEY}}", html.escape(item_key))
        .replace("{{DATE}}", html.escape(digest_date))
    )


def error_html(message: str) -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>"
        f"<h2>反馈失败</h2><p>{html.escape(message)}</p>"
        "</body></html>"
    )


def render_confirm_page(
    *,
    signal: str,
    item_type: str,
    item_key: str,
    digest_date: str,
) -> str:
    return _confirm_html(
        signal=signal,
        item_type=item_type,
        item_key=item_key,
        digest_date=digest_date,
    )


def _since(days: int) -> datetime:
    tz = ZoneInfo(settings.scheduler_timezone)
    now = datetime.now(tz=tz)
    return now - timedelta(days=days)


def _ai_bucket(rating: float | None) -> str:
    if rating is None:
        return "无 AI 分"
    if rating >= 8.0:
        return "8+"
    if rating >= 7.0:
        return "7-8"
    if rating >= 6.0:
        return "6-7"
    return "<6"


def _lookup_ai_ratings(session: Session, rows: list[UserFeedback]) -> dict[tuple[str, str], float | None]:
    out: dict[tuple[str, str], float | None] = {}
    for fb in rows:
        key = (fb.item_type, fb.item_key)
        if key in out:
            continue
        if fb.item_type == "github":
            rating = session.scalar(
                select(GitHubProject.ai_rating)
                .where(GitHubProject.repo_name == fb.item_key)
                .order_by(GitHubProject.id.desc())
                .limit(1)
            )
        else:
            rating = session.scalar(
                select(ArxivPaper.ai_rating)
                .where(ArxivPaper.paper_url.contains(fb.item_key))
                .order_by(ArxivPaper.id.desc())
                .limit(1)
            )
        out[key] = float(rating) if rating is not None else None
    return out


def build_feedback_report(session: Session, *, days: int = 7) -> str:
    since = _since(days)
    rows = session.scalars(
        select(UserFeedback)
        .where(UserFeedback.created_at >= since)
        .order_by(UserFeedback.created_at.desc())
    ).all()

    up = sum(1 for r in rows if r.signal == "up")
    down = sum(1 for r in rows if r.signal == "down")
    rated = up + down
    precision = (up / rated * 100.0) if rated else 0.0

    lines: list[str] = [
        f"【反馈周报】近 {days} 天",
        "",
        f"反馈总数：{len(rows)}（👍 {up} / 👎 {down}）",
        f"Precision@反馈：{precision:.1f}%（👍 / (👍+👎)，未反馈条目不计入）",
        "",
    ]

    ai_map = _lookup_ai_ratings(session, rows)
    buckets: dict[str, list[str]] = {}
    for fb in rows:
        rating = ai_map.get((fb.item_type, fb.item_key))
        bucket = _ai_bucket(rating)
        buckets.setdefault(bucket, []).append(fb.signal)

    lines.append("AI 分桶校准（按有反馈条目）：")
    for bucket in ("8+", "7-8", "6-7", "<6", "无 AI 分"):
        sigs = buckets.get(bucket, [])
        if not sigs:
            continue
        b_up = sum(1 for s in sigs if s == "up")
        b_total = len(sigs)
        lines.append(f"  {bucket}: 👍率 {b_up / b_total * 100:.0f}% ({b_up}/{b_total})")
    lines.append("")

    down_rows = [r for r in rows if r.signal == "down"]
    if down_rows:
        lines.append("本周 👎 条目：")
        for r in down_rows:
            rating = ai_map.get((r.item_type, r.item_key))
            rating_s = f"{rating:.1f}" if rating is not None else "—"
            lines.append(f"  [{r.item_type}] {r.item_key}（AI {rating_s}，{r.digest_date}）")
        lines.append("")

    agg = session.execute(
        select(
            UserFeedback.item_type,
            UserFeedback.item_key,
            func.sum(
                case((UserFeedback.signal == "down", 1), else_=0)
            ).label("down_count"),
        ).group_by(UserFeedback.item_type, UserFeedback.item_key)
    ).all()

    heavy = [
        (t, k, int(c or 0))
        for t, k, c in agg
        if int(c or 0) >= 2
    ]
    if heavy:
        lines.append("累计 👎 ≥ 2（当前降权）：")
        for t, k, c in sorted(heavy, key=lambda x: -x[2]):
            pen = penalty_for_down_count(c)
            lines.append(f"  [{t}] {k}：👎×{c}，扣分 -{pen:.0f}")
        lines.append("")

    if not rows:
        lines.append("（本周暂无反馈记录）")

    return "\n".join(lines).strip()


def run_feedback_report(*, days: int = 7, email: bool = False) -> str:
    from app.db.session import get_session, init_db

    init_db()
    session = get_session()
    try:
        report = build_feedback_report(session, days=days)
    finally:
        session.close()

    if email:
        if not email_notify_configured():
            raise RuntimeError("未配置邮件，无法 --email-report")
        send_report_email(report, days=days)
    return report
