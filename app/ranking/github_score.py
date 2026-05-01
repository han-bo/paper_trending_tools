from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

# Hanbo 维度（文档）：技术壁垒 30% / 商业价值 30% / 可复制性 20% / 投入成本 10% / 长期价值 10%
# 规则层用可观测工程指标近似，最终与 LLM 评分按文档「工程分 + AI 判断分」合并。

_ENG_MAX = 50.0
_AI_MAX = 50.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _days_since(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=dt.tzinfo)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def compute_engineering_score(repo: dict[str, Any]) -> float:
    """工程分（0~50）：Stars 增速、Commit 活跃度、Contributor、Issue、Release 等可量化信号。"""
    stars = float(repo.get("stars") or 0)
    stars_growth = float(repo.get("stars_growth") or 0)
    contributors = float(repo.get("contributors") or 0)
    releases = float(repo.get("release_count") or 0)
    issues = float(repo.get("issue_count") or 0)
    last_commit = repo.get("last_commit_at")

    # Stars 水平（对数饱和）
    star_part = 12.0 * _clamp(math.log10(stars + 10.0) / math.log10(50000.0), 0.0, 1.0)
    # Stars 增速（个人版：来自与历史快照的差分）
    growth_part = 8.0 * _clamp(stars_growth / 500.0, 0.0, 1.0)
    # 贡献者规模
    contrib_part = 10.0 * _clamp(contributors / 80.0, 0.0, 1.0)
    # Release 频率
    release_part = 8.0 * _clamp(releases / 30.0, 0.0, 1.0)
    # Issue 活跃度（中等区间更优，避免 0 或极端大）
    issue_part = 6.0 * _clamp(1.0 - abs(issues - 25.0) / 80.0, 0.0, 1.0)
    # 最近提交
    days = _days_since(last_commit)
    if days is None:
        commit_part = 2.0
    else:
        commit_part = 6.0 * _clamp(1.0 - days / 21.0, 0.0, 1.0)

    raw = star_part + growth_part + contrib_part + release_part + issue_part + commit_part
    return float(_clamp(raw, 0.0, _ENG_MAX))


def combine_github_scores(engineering: float, ai_rating_1_to_10: float | None) -> float:
    """综合评分 = 工程分（0~50）+ AI 判断分（0~50，对应 1~10 分线性映射）。"""
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
