"""每日摘要邮件推送（Zoho Mail REST API，HTTPS）。"""

from __future__ import annotations

from app.config import settings
from app.notifier.zoho_mail import (
    send_digest_zoho_mail,
    zoho_mail_notify_configured,
)


def _recipients() -> list[str]:
    raw = settings.digest_email_to.strip()
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def send_digest_email(content: str) -> None:
    """发送 UTF-8 纯文本摘要。"""
    if not zoho_mail_notify_configured():
        raise RuntimeError(
            "未配置 Zoho Mail API：请填写 ZOHO_ACCOUNTS_BASE、ZOHO_MAIL_API_BASE、"
            "ZOHO_OAUTH_CLIENT_ID、ZOHO_OAUTH_CLIENT_SECRET、ZOHO_OAUTH_REFRESH_TOKEN、"
            "ZOHO_MAIL_FROM"
        )
    to_addrs = _recipients()
    if not to_addrs:
        raise RuntimeError("未配置 DIGEST_EMAIL_TO（收件人，多个用英文逗号分隔）")
    send_digest_zoho_mail(
        content,
        to_addrs=to_addrs,
        subject=settings.digest_email_subject,
        from_addr=settings.zoho_mail_from.strip(),
    )


def email_notify_configured() -> bool:
    return zoho_mail_notify_configured() and bool(_recipients())
