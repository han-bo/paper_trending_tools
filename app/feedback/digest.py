from __future__ import annotations

import html
from dataclasses import dataclass

from app.feedback.links import build_feedback_url, feedback_configured


@dataclass
class DigestItem:
    item_type: str
    item_key: str
    title: str
    reason: str
    score: float
    effective_score: float
    url: str
    feedback_up_url: str = ""
    feedback_down_url: str = ""


def attach_feedback_links(items: list[DigestItem], digest_date: str) -> list[DigestItem]:
    if not feedback_configured():
        return items
    out: list[DigestItem] = []
    for it in items:
        out.append(
            DigestItem(
                item_type=it.item_type,
                item_key=it.item_key,
                title=it.title,
                reason=it.reason,
                score=it.score,
                effective_score=it.effective_score,
                url=it.url,
                feedback_up_url=build_feedback_url(
                    signal="up",
                    item_type=it.item_type,
                    item_key=it.item_key,
                    digest_date=digest_date,
                ),
                feedback_down_url=build_feedback_url(
                    signal="down",
                    item_type=it.item_type,
                    item_key=it.item_key,
                    digest_date=digest_date,
                ),
            )
        )
    return out


def render_digest_text(
    *,
    digest_date: str,
    github_items: list[DigestItem],
    arxiv_items: list[DigestItem],
    suggest_pick: str,
    include_feedback_links: bool = False,
) -> str:
    lines: list[str] = ["【今日值得关注】", "", f"GitHub Top {len(github_items)}", ""]
    for idx, it in enumerate(github_items, start=1):
        lines.append(f"{idx}. {it.title}")
        lines.append(f"原因：{it.reason or '（规则层排序，尚未生成摘要）'}")
        lines.append(f"评分：{it.effective_score:.1f}")
        lines.append(f"链接：{it.url}")
        if include_feedback_links and it.feedback_up_url:
            lines.append(f"反馈：👍 {it.feedback_up_url}")
            lines.append(f"      👎 {it.feedback_down_url}")
        lines.append("")

    lines.append(f"arXiv Top {len(arxiv_items)}")
    lines.append("")
    for idx, it in enumerate(arxiv_items, start=1):
        lines.append(f"{idx}. {it.title}")
        lines.append(f"原因：{it.reason or '（规则层排序，尚未生成摘要）'}")
        lines.append(f"评分：{it.effective_score:.1f}")
        lines.append(f"链接：{it.url}")
        if include_feedback_links and it.feedback_up_url:
            lines.append(f"反馈：👍 {it.feedback_up_url}")
            lines.append(f"      👎 {it.feedback_down_url}")
        lines.append("")

    lines.append("建议：")
    lines.append(f"今天最值得深入研究的是：{suggest_pick}")
    return "\n".join(lines).strip()


def _score_note(it: DigestItem) -> str:
    if abs(it.effective_score - it.score) > 0.05:
        return f"{it.effective_score:.1f}（原 {it.score:.1f}，已因历史反馈降权）"
    return f"{it.effective_score:.1f}"


def _feedback_buttons(it: DigestItem) -> str:
    if not it.feedback_up_url:
        return ""
    return (
        '<p style="margin:8px 0 16px;">'
        f'<a href="{html.escape(it.feedback_up_url)}" '
        'style="display:inline-block;padding:6px 14px;margin-right:8px;'
        'background:#e8f5e9;color:#2e7d32;text-decoration:none;border-radius:4px;">'
        "👍 值得</a>"
        f'<a href="{html.escape(it.feedback_down_url)}" '
        'style="display:inline-block;padding:6px 14px;'
        'background:#ffebee;color:#c62828;text-decoration:none;border-radius:4px;">'
        "👎 不满意</a>"
        "</p>"
    )


def _render_item_block(it: DigestItem, index: int) -> str:
    reason = html.escape(it.reason or "（规则层排序，尚未生成摘要）")
    title = html.escape(it.title)
    url = html.escape(it.url)
    score = html.escape(_score_note(it))
    return (
        f"<h3 style=\"margin:16px 0 4px;\">{index}. {title}</h3>"
        f"<p style=\"margin:4px 0;\"><strong>原因：</strong>{reason}</p>"
        f"<p style=\"margin:4px 0;\"><strong>评分：</strong>{score}</p>"
        f'<p style="margin:4px 0;"><a href="{url}">{url}</a></p>'
        f"{_feedback_buttons(it)}"
    )


def render_digest_html(
    *,
    digest_date: str,
    github_items: list[DigestItem],
    arxiv_items: list[DigestItem],
    suggest_pick: str,
) -> str:
    parts: list[str] = [
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>",
        "<h2>【今日值得关注】</h2>",
        f"<p style=\"color:#666;\">日期：{html.escape(digest_date)}</p>",
        f"<h2>GitHub Top {len(github_items)}</h2>",
    ]
    for idx, it in enumerate(github_items, start=1):
        parts.append(_render_item_block(it, idx))
    parts.append(f"<h2>arXiv Top {len(arxiv_items)}</h2>")
    for idx, it in enumerate(arxiv_items, start=1):
        parts.append(_render_item_block(it, idx))
    parts.append("<h2>建议</h2>")
    parts.append(f"<p>今天最值得深入研究的是：<strong>{html.escape(suggest_pick)}</strong></p>")
    parts.append("</body></html>")
    return "".join(parts)
