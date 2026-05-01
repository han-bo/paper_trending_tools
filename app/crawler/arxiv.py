from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
from loguru import logger

from app.config import settings

_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?",
    re.IGNORECASE,
)


def _parse_published(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _first_github_url(text: str | None) -> str | None:
    if not text:
        return None
    m = _GITHUB_URL_RE.search(text)
    return m.group(0).rstrip("/") if m else None


def _pdf_from_arxiv_id(arxiv_id: str) -> str | None:
    if not arxiv_id:
        return None
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _arxiv_id_from_link(link: str) -> str | None:
    if not link:
        return None
    path = urlparse(link).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "abs":
        return parts[1]
    if len(parts) >= 2 and parts[0] == "pdf":
        return parts[1].replace(".pdf", "")
    return None


def fetch_arxiv_entries() -> list[dict[str, Any]]:
    urls = [u.strip() for u in settings.arxiv_rss_urls.split(",") if u.strip()]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url in urls:
        logger.info("抓取 arXiv RSS: {}", url)
        parsed = feedparser.parse(url)
        for entry in parsed.entries[: settings.arxiv_max_entries]:
            title = (getattr(entry, "title", "") or "").replace("\n", " ").strip()
            link = getattr(entry, "link", "") or ""
            if not title or not link:
                continue
            key = link
            if key in seen:
                continue
            seen.add(key)
            summary = getattr(entry, "summary", None) or getattr(entry, "description", None) or ""
            summary_text = re.sub(r"<[^>]+>", "", summary).strip()
            authors = getattr(entry, "author", None)
            if not authors:
                authors = ", ".join(a.get("name", "") for a in getattr(entry, "authors", []) if a.get("name"))
            categories = []
            for t in getattr(entry, "tags", []) or []:
                term = t.get("term") if isinstance(t, dict) else getattr(t, "term", None)
                if term:
                    categories.append(term)
            category = ",".join(categories) if categories else None
            published_at = _parse_published(entry)
            arxiv_id = _arxiv_id_from_link(link)
            pdf_url = _pdf_from_arxiv_id(arxiv_id) if arxiv_id else None
            gh = _first_github_url(summary_text) or _first_github_url(title)
            out.append(
                {
                    "title": title,
                    "authors": authors or None,
                    "abstract": summary_text or None,
                    "paper_url": link,
                    "pdf_url": pdf_url,
                    "category": category,
                    "published_at": published_at,
                    "github_repo_url": gh,
                }
            )
    return out
