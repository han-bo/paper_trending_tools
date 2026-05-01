from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from loguru import logger

from app.config import settings


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _get_json(url: str, params: dict | None = None) -> Any:
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=60)
    if r.status_code == 403:
        logger.warning("GitHub API 403: {}", r.text[:240])
    r.raise_for_status()
    return r.json()


def _count_contributors(owner: str, repo: str) -> int:
    """统计贡献者数量；超大仓库 API 可能拒绝或网络抖动，返回已统计值或 0。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    total = 0
    page = 1
    per_page = 100
    while page <= 3:
        try:
            batch = _get_json(url, params={"per_page": per_page, "page": page})
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 422):
                logger.warning("contributors 接口不可用 {}: {}", f"{owner}/{repo}", e)
                return total
            logger.warning("contributors HTTP 错误 {}: {}", f"{owner}/{repo}", e)
            return total
        except requests.RequestException as e:
            logger.warning("contributors 请求失败 {}: {}", f"{owner}/{repo}", e)
            return total
        if not isinstance(batch, list) or len(batch) == 0:
            break
        total += len(batch)
        if len(batch) < per_page:
            break
        page += 1
    return total


def _count_releases(owner: str, repo: str) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    total = 0
    page = 1
    per_page = 100
    while page <= 3:
        try:
            batch = _get_json(url, params={"per_page": per_page, "page": page})
        except requests.RequestException as e:
            logger.warning("releases 请求失败 {}: {}", f"{owner}/{repo}", e)
            return total
        if not isinstance(batch, list) or len(batch) == 0:
            break
        total += len(batch)
        if len(batch) < per_page:
            break
        page += 1
    return total


def _fetch_readme(owner: str, repo: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    try:
        data = _get_json(url)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    content = data.get("content")
    encoding = data.get("encoding")
    if not content or encoding != "base64":
        return None
    try:
        return base64.b64decode(content).decode("utf-8", errors="replace")[:80000]
    except Exception:
        return None


def _last_commit_at(owner: str, repo: str) -> datetime | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    data = _get_json(url, params={"per_page": 1})
    if not isinstance(data, list) or not data:
        return None
    cdate = (
        data[0].get("commit", {})
        .get("committer", {})
        .get("date")
        or data[0].get("commit", {}).get("author", {}).get("date")
    )
    if not cdate:
        return None
    try:
        return datetime.fromisoformat(cdate.replace("Z", "+00:00"))
    except ValueError:
        return None


def search_hot_repositories() -> list[dict[str, Any]]:
    """搜索近期活跃的高星仓库，返回标准化字段。"""
    pushed_since = (date.today() - timedelta(days=settings.github_pushed_days)).isoformat()
    q = f"{settings.github_search_query} pushed:>{pushed_since}"
    url = "https://api.github.com/search/repositories"
    data = _get_json(
        url,
        params={
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": settings.github_per_page,
        },
    )
    items = data.get("items") or []
    out: list[dict[str, Any]] = []
    for it in items:
        full = it.get("full_name") or ""
        if "/" not in full:
            continue
        owner, name = full.split("/", 1)
        repo_url = it.get("html_url") or ""
        stars = int(it.get("stargazers_count") or 0)
        open_issues = int(it.get("open_issues_count") or 0)
        language = it.get("language")
        topics = it.get("topics") or []
        description = (it.get("description") or "").strip()
        try:
            contributors = _count_contributors(owner, name)
            release_count = _count_releases(owner, name)
            last_commit = _last_commit_at(owner, name)
            readme = _fetch_readme(owner, name)
        except requests.RequestException as e:
            logger.warning("拉取仓库详情失败 {}: {}", full, e)
            continue
        out.append(
            {
                "repo_name": full,
                "repo_url": repo_url,
                "stars": stars,
                "contributors": contributors,
                "last_commit_at": last_commit,
                "issue_count": open_issues,
                "release_count": release_count,
                "language": language,
                "topic": ",".join(topics) if topics else None,
                "raw_readme": readme,
                "description": description,
                "recent_activity": _recent_activity_summary(last_commit, open_issues, release_count),
            }
        )
    return out


def _recent_activity_summary(
    last_commit: datetime | None,
    open_issues: int,
    release_count: int,
) -> str:
    parts: list[str] = []
    if last_commit:
        parts.append(f"最近提交时间：{last_commit.astimezone(timezone.utc).date().isoformat()}")
    parts.append(f"开放 Issue 约 {open_issues} 个")
    parts.append(f"Release 数量约 {release_count}（近期分页统计）")
    return "；".join(parts)
