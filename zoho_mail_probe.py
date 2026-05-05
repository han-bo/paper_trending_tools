#!/usr/bin/env python3
"""Zoho Mail API 测试发信：与每日摘要相同的 OAuth + /messages 流程。

在项目根目录执行（需已配置 .env 中 ZOHO_* 与 DIGEST_EMAIL_TO）：

    .venv/bin/python zoho_mail_probe.py

或指定收件人、只测 OAuth 不写库：

    .venv/bin/python zoho_mail_probe.py --to you@example.com --dry-run
"""

from __future__ import annotations

import argparse
import sys

from app.config import settings
from app.notifier.zoho_mail import (
    _zoho_access_token,
    _zoho_account_id,
    send_digest_zoho_mail,
    zoho_mail_notify_configured,
)


def _recipients_from_env() -> list[str]:
    raw = settings.digest_email_to.strip()
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Zoho Mail API 测试发信")
    parser.add_argument(
        "--to",
        default="",
        help="收件人（可多个，英文逗号分隔）；默认取 DIGEST_EMAIL_TO",
    )
    parser.add_argument(
        "--subject",
        default="【测试】Zoho Mail API 连通性",
        help="邮件主题",
    )
    parser.add_argument(
        "--body",
        default=(
            "这是一封由 paper_trending_tools 的 zoho_mail_probe.py "
            "发出的测试邮件。\n若收到说明 OAuth 与发信接口正常。"
        ),
        help="正文（纯文本）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只换 access_token 并解析 accountId，不调用发信接口",
    )
    args = parser.parse_args()

    if not zoho_mail_notify_configured():
        print(
            "[FAIL] Zoho Mail API 未配齐：请检查 .env 中 "
            "ZOHO_ACCOUNTS_BASE、ZOHO_MAIL_API_BASE、"
            "ZOHO_OAUTH_CLIENT_ID、ZOHO_OAUTH_CLIENT_SECRET、"
            "ZOHO_OAUTH_REFRESH_TOKEN、ZOHO_MAIL_FROM",
            file=sys.stderr,
        )
        return 2

    if args.to.strip():
        to_addrs = [a.strip() for a in args.to.split(",") if a.strip()]
    else:
        to_addrs = _recipients_from_env()

    if not to_addrs:
        print(
            "[FAIL] 无收件人：请设置 --to 或在 .env 中配置 DIGEST_EMAIL_TO",
            file=sys.stderr,
        )
        return 2

    from_addr = settings.zoho_mail_from.strip()

    try:
        token = _zoho_access_token()
        acct = _zoho_account_id(token)
        print(f"[OK] OAuth access_token 已获取（长度 {len(token)}）")
        print(f"[OK] accountId = {acct}")
    except Exception as e:
        print(f"[FAIL] OAuth 或账户解析: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[OK] --dry-run：跳过发信")
        return 0

    try:
        send_digest_zoho_mail(
            args.body,
            to_addrs=to_addrs,
            subject=args.subject,
            from_addr=from_addr,
        )
    except Exception as e:
        print(f"[FAIL] 发信: {e}", file=sys.stderr)
        return 1

    print(f"[OK] 已发送至: {', '.join(to_addrs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
