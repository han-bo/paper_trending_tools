from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserFeedback


def record_feedback(
    session: Session,
    *,
    item_type: str,
    item_key: str,
    digest_date: str,
    signal: str,
) -> UserFeedback:
    if signal not in ("up", "down"):
        raise ValueError(f"invalid signal: {signal!r}")
    existing = session.scalar(
        select(UserFeedback).where(
            UserFeedback.item_type == item_type,
            UserFeedback.item_key == item_key,
            UserFeedback.digest_date == digest_date,
        )
    )
    if existing:
        existing.signal = signal
        existing.created_at = datetime.now().astimezone()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    row = UserFeedback(
        item_type=item_type,
        item_key=item_key,
        digest_date=digest_date,
        signal=signal,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
