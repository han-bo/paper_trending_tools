from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserFeedback


def penalty_for_down_count(down_count: int) -> float:
    if down_count <= 0:
        return 0.0
    raw = float(down_count) * settings.feedback_penalty_per_down
    return min(settings.feedback_penalty_cap, raw)


def load_penalty_map(session: Session) -> dict[tuple[str, str], float]:
    """按 (item_type, item_key) 聚合历史 👎 次数并换算为扣分。"""
    rows = session.execute(
        select(
            UserFeedback.item_type,
            UserFeedback.item_key,
            func.sum(
                case((UserFeedback.signal == "down", 1), else_=0)
            ).label("down_count"),
        ).group_by(UserFeedback.item_type, UserFeedback.item_key)
    ).all()
    out: dict[tuple[str, str], float] = {}
    for item_type, item_key, down_count in rows:
        penalty = penalty_for_down_count(int(down_count or 0))
        if penalty > 0:
            out[(str(item_type), str(item_key))] = penalty
    return out


def effective_score(
    base_score: float,
    *,
    item_type: str,
    item_key: str,
    penalty_map: dict[tuple[str, str], float],
) -> float:
    penalty = penalty_map.get((item_type, item_key), 0.0)
    return max(0.0, float(base_score) - penalty)
