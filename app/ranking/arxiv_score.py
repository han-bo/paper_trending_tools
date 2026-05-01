from __future__ import annotations

import math
import re
from typing import Any

_ENG_MAX = 50.0
_AI_MAX = 50.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_engineering_score(paper: dict[str, Any]) -> float:
    """arXiv 规则层工程分（0~50）：是否附代码、摘要信息量、分类信号等。"""
    abstract = (paper.get("abstract") or "").strip()
    has_code = bool(paper.get("github_repo_url"))
    category = (paper.get("category") or "").lower()

    code_part = 14.0 if has_code else 4.0
    len_part = 12.0 * _clamp(len(abstract) / 1200.0, 0.0, 1.0)

    hot_kw = ("llm", "agent", "diffusion", "reasoning", "multimodal", "robot", "embodied")
    kw_hits = sum(1 for k in hot_kw if k in abstract.lower() or k in category)
    topic_part = 10.0 * _clamp(kw_hits / 4.0, 0.0, 1.0)

    author_str = paper.get("authors") or ""
    author_part = 8.0 * _clamp(len(re.split(r"[,;]", author_str)) / 8.0, 0.0, 1.0)

    math_density = len(re.findall(r"\\[a-zA-Z]+|theorem|lemma|proof", abstract.lower()))
    theory_part = 6.0 * _clamp(math_density / 6.0, 0.0, 1.0)

    raw = code_part + len_part + topic_part + author_part + theory_part
    # 文档强调「工程落地价值」：过强理论关键词略降权
    if theory_part >= 5.0 and not has_code:
        raw -= 4.0
    return float(_clamp(raw, 0.0, _ENG_MAX))


def combine_arxiv_scores(engineering: float, ai_rating_1_to_10: float | None) -> float:
    eng = _clamp(engineering, 0.0, _ENG_MAX)
    if ai_rating_1_to_10 is None:
        return float(_clamp(eng, 0.0, 100.0))
    ai = _clamp(float(ai_rating_1_to_10), 1.0, 10.0)
    ai_part = (ai / 10.0) * _AI_MAX
    return float(_clamp(eng + ai_part, 0.0, 100.0))


def worth_follow_from_ai_rating(ai_rating_1_to_10: float | None) -> bool:
    if ai_rating_1_to_10 is None:
        return False
    return float(ai_rating_1_to_10) >= 7.0
