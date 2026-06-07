from __future__ import annotations

import re

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def github_item_key(repo_name: str) -> str:
    return repo_name.strip()


def arxiv_item_key(paper_url: str) -> str:
    url = (paper_url or "").strip()
    m = _ARXIV_ID_RE.search(url)
    if m:
        return m.group(1)
    tail = url.rstrip("/").split("/")[-1]
    if tail:
        return tail.split("v", 1)[0]
    return url


def item_key_for_row(item_type: str, row: dict) -> str:
    if item_type == "github":
        return github_item_key(str(row.get("repo_name") or ""))
    if item_type == "arxiv":
        return arxiv_item_key(str(row.get("paper_url") or ""))
    raise ValueError(f"unknown item_type: {item_type!r}")
