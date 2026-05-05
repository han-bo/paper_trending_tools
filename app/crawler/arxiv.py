from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlparse

import feedparser
import httpx
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


def _arxiv_category_from_rss_url(url: str) -> str | None:
    """从 arXiv 分类 RSS 地址解析 slug，例如 .../rss/cs.AI -> cs.AI。"""
    try:
        segs = [s for s in urlparse(url.strip()).path.split("/") if s]
    except (TypeError, ValueError):
        return None
    if len(segs) >= 2 and segs[-2].lower() == "rss":
        return segs[-1]
    return None


def _arxiv_api_feed_url(category: str, max_results: int) -> str:
    q = urlencode(
        {
            "search_query": f"cat:{category}",
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    return f"http://export.arxiv.org/api/query?{q}"


def _fetch_arxiv_feed_xml(url: str) -> str | None:
    """用 httpx 下载 feed，带 User-Agent，避免默认客户端被限频或返回非 XML。"""
    ua = (settings.arxiv_http_user_agent or "").strip() or "paper_trending_tools/1.0"
    try:
        r = httpx.get(
            url,
            timeout=httpx.Timeout(60.0, connect=30.0),
            follow_redirects=True,
            headers={"User-Agent": ua},
        )
    except httpx.RequestError as e:
        logger.warning("下载 arXiv feed 失败 {}: {}", url, e)
        return None
    if r.status_code == 429:
        logger.warning("arXiv 返回 429（请求过频），请稍后再试: {}", url)
        return None
    if r.status_code != 200:
        logger.warning("下载 arXiv feed HTTP {}: {}", r.status_code, url)
        return None
    text = r.text.strip()
    if not text or text.lower().startswith("rate exceeded"):
        logger.warning("arXiv feed 正文异常（可能限频）: {}", url)
        return None
    return r.text


def _feed_entries_for_arxiv_source(rss_url: str, max_entries: int) -> list[Any]:
    """
    优先请求分类 RSS；若 channel 内无 item（arXiv 常如此），则回退 Atom API，
    否则会出现「解析成功但 0 条」。
    """
    logger.info("抓取 arXiv RSS: {}", rss_url)
    xml = _fetch_arxiv_feed_xml(rss_url)
    if xml is None:
        return []
    parsed = feedparser.parse(xml)
    entries = list(parsed.entries[:max_entries])
    if entries:
        return entries
    cat = _arxiv_category_from_rss_url(rss_url)
    if not cat:
        logger.warning("RSS 无条目且无法从 URL 解析 arXiv 分类，跳过: {}", rss_url)
        return []
    api_url = _arxiv_api_feed_url(cat, max_entries)
    logger.info("RSS 无条目，回退 arXiv API（cat:{}）: {}", cat, api_url)
    xml = _fetch_arxiv_feed_xml(api_url)
    if xml is None:
        return []
    parsed = feedparser.parse(xml)
    if getattr(parsed, "bozo", False) and getattr(parsed, "bozo_exception", None):
        logger.warning("arXiv API feed 解析告警: {}", parsed.bozo_exception)
    return list(parsed.entries[:max_entries])


def fetch_arxiv_entries() -> list[dict[str, Any]]:
    urls = [u.strip() for u in settings.arxiv_rss_urls.split(",") if u.strip()]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url in urls:
        for entry in _feed_entries_for_arxiv_source(url, settings.arxiv_max_entries):
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
