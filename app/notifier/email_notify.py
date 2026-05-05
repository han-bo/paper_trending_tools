"""每日摘要邮件推送（标准库 smtplib，无额外依赖）。"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from loguru import logger

from app.config import settings


def _recipients() -> list[str]:
    raw = settings.digest_email_to.strip()
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def send_digest_email(content: str) -> None:
    """发送 UTF-8 纯文本摘要。需配置 SMTP_HOST、SMTP_FROM、DIGEST_EMAIL_TO。"""
    if not settings.smtp_host:
        raise RuntimeError("未配置 SMTP_HOST")
    if not settings.smtp_from.strip():
        raise RuntimeError("未配置 SMTP_FROM（发件人地址）")
    to_addrs = _recipients()
    if not to_addrs:
        raise RuntimeError("未配置 DIGEST_EMAIL_TO（收件人，多个用英文逗号分隔）")

    msg = EmailMessage()
    msg["Subject"] = settings.digest_email_subject
    msg["From"] = settings.smtp_from.strip()
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(content, charset="utf-8")

    host = settings.smtp_host.strip()
    port = settings.smtp_port
    user = settings.smtp_user.strip()
    password = settings.smtp_password

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=90) as smtp:
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=90) as smtp:
            smtp.ehlo()
            if settings.smtp_starttls:
                smtp.starttls()
                smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)

    logger.info("邮件摘要已发送至 {}", to_addrs)


def email_notify_configured() -> bool:
    return bool(
        settings.smtp_host.strip()
        and settings.smtp_from.strip()
        and _recipients()
    )
