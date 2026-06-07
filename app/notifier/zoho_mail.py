"""Zoho Mail REST API 发信（HTTPS）。"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings


def zoho_mail_notify_configured() -> bool:
    return bool(
        settings.zoho_accounts_base.strip()
        and settings.zoho_mail_api_base.strip()
        and settings.zoho_oauth_client_id.strip()
        and settings.zoho_oauth_client_secret.strip()
        and settings.zoho_oauth_refresh_token.strip()
        and settings.zoho_mail_from.strip()
    )


def _zoho_access_token() -> str:
    base = settings.zoho_accounts_base.strip().rstrip("/")
    r = httpx.post(
        f"{base}/oauth/v2/token",
        data={
            "refresh_token": settings.zoho_oauth_refresh_token.strip(),
            "client_id": settings.zoho_oauth_client_id.strip(),
            "client_secret": settings.zoho_oauth_client_secret.strip(),
            "grant_type": "refresh_token",
        },
        timeout=httpx.Timeout(60.0, connect=30.0),
    )
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        raise RuntimeError(
            f"Zoho OAuth 失败 HTTP {r.status_code}: {body or r.text[:500]}"
        )
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Zoho OAuth 响应无 access_token: {body}")
    return str(token)


def _zoho_account_id(token: str) -> str:
    configured = settings.zoho_mail_account_id.strip()
    if configured:
        return configured
    base = settings.zoho_mail_api_base.strip().rstrip("/")
    r = httpx.get(
        f"{base}/api/accounts",
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        timeout=httpx.Timeout(60.0, connect=30.0),
    )
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        raise RuntimeError(
            f"Zoho 获取账户失败 HTTP {r.status_code}: {body or r.text[:500]}"
        )
    rows = body.get("data") or []
    if not rows:
        raise RuntimeError(
            "Zoho Mail /api/accounts 无账户，请在 .env 中配置 ZOHO_MAIL_ACCOUNT_ID"
        )
    return str(rows[0]["accountId"])


def send_digest_zoho_mail(
    content: str,
    *,
    to_addrs: list[str],
    subject: str,
    from_addr: str,
    mail_format: str = "plaintext",
) -> None:
    """按 Zoho Mail API 逐封发送（每收件人一封，与 API 字段一致）。"""
    token = _zoho_access_token()
    account_id = _zoho_account_id(token)
    base = settings.zoho_mail_api_base.strip().rstrip("/")
    url = f"{base}/api/accounts/{account_id}/messages"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    fmt = mail_format if mail_format in ("plaintext", "html") else "plaintext"
    payload_base = {
        "fromAddress": from_addr.strip(),
        "subject": subject,
        "content": content,
        "mailFormat": fmt,
    }
    for to in to_addrs:
        r = httpx.post(
            url,
            headers=headers,
            json={**payload_base, "toAddress": to},
            timeout=httpx.Timeout(120.0, connect=30.0),
        )
        try:
            body = r.json()
        except Exception:
            body = {}
        if r.status_code >= 400:
            raise RuntimeError(
                f"Zoho 发信失败 HTTP {r.status_code} -> {to!r}: "
                f"{body or r.text[:500]}"
            )
    logger.info("Zoho Mail 摘要已发送至 {}", to_addrs)
