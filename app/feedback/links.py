from __future__ import annotations

import hmac
import hashlib
from urllib.parse import urlencode

from app.config import settings

_TYPE_TO_CODE = {"github": "gh", "arxiv": "ax"}
_CODE_TO_TYPE = {v: k for k, v in _TYPE_TO_CODE.items()}


def feedback_configured() -> bool:
    return bool(settings.feedback_base_url.strip() and settings.feedback_hmac_secret.strip())


def item_type_code(item_type: str) -> str:
    code = _TYPE_TO_CODE.get(item_type)
    if not code:
        raise ValueError(f"unknown item_type: {item_type!r}")
    return code


def item_type_from_code(code: str) -> str:
    item_type = _CODE_TO_TYPE.get(code)
    if not item_type:
        raise ValueError(f"unknown type code: {code!r}")
    return item_type


def _sign_payload(*, item_type: str, item_key: str, digest_date: str, signal: str) -> str:
    secret = settings.feedback_hmac_secret.strip()
    payload = f"{item_type}|{item_key}|{digest_date}|{signal}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]


def verify_signature(
    *,
    item_type: str,
    item_key: str,
    digest_date: str,
    signal: str,
    sig: str,
) -> bool:
    if not settings.feedback_hmac_secret.strip():
        return False
    expected = _sign_payload(
        item_type=item_type,
        item_key=item_key,
        digest_date=digest_date,
        signal=signal,
    )
    return hmac.compare_digest(expected, sig)


def build_feedback_url(
    *,
    signal: str,
    item_type: str,
    item_key: str,
    digest_date: str,
) -> str:
    base = settings.feedback_base_url.strip().rstrip("/")
    sig = _sign_payload(
        item_type=item_type,
        item_key=item_key,
        digest_date=digest_date,
        signal=signal,
    )
    qs = urlencode(
        {
            "t": item_type_code(item_type),
            "k": item_key,
            "d": digest_date,
            "sig": sig,
        }
    )
    return f"{base}/f/{signal}?{qs}"
