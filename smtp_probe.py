#!/usr/bin/env python3
"""SMTP 诊断脚本：定位连接、TLS、认证、发件各阶段问题。"""

from __future__ import annotations

import argparse
import os
import smtplib
import socket
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path


def load_dotenv_if_exists(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def get_env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return default if v is None else v


def print_ok(step: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[OK] {step}{suffix}")


def print_fail(step: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[FAIL] {step}{suffix}")


def explain_common_causes(step: str, exc: Exception | None = None) -> None:
    print("可能原因：")
    if step == "dns":
        print("  1) SMTP_HOST 拼写错误，或区域域名用错（如应使用 .eu/.com.cn）。")
        print("  2) 机器 DNS 配置异常，无法解析外网域名。")
        print("  3) 网络环境限制外网 DNS 查询。")
    elif step == "tcp":
        print("  1) 当前网络/防火墙阻断了 SMTP 端口（常见 587/465 被封）。")
        print("  2) SMTP_HOST 或 SMTP_PORT 不匹配服务端要求。")
        print("  3) 目标服务短时不可达，或你所在机器到该机房链路不通。")
    elif step == "tls":
        print("  1) STARTTLS/SSL 模式配错（587 通常 STARTTLS，465 通常 SSL）。")
        print("  2) 本机时间不准导致证书校验失败。")
        print("  3) 企业代理/中间设备拦截 TLS。")
    elif step == "auth":
        print("  1) SMTP_USER / SMTP_PASSWORD 错误。")
        print("  2) 服务商要求应用专用密码（普通登录密码不可用）。")
        print("  3) 账号未开启 SMTP/IMAP/POP 权限，或触发风控。")
    elif step == "send":
        print("  1) 发件人地址与账号不一致，服务商拒绝中继。")
        print("  2) 收件人地址格式不合法。")
        print("  3) 账号权限限制了外发或该收件域名。")
    else:
        print("  1) 网络不稳定或服务端临时异常。")
        print("  2) 环境变量配置不完整。")
    if exc is not None:
        print(f"异常信息：{type(exc).__name__}: {exc}")


def require_non_empty(name: str, value: str) -> None:
    if value.strip():
        return
    raise ValueError(f"缺少必填配置：{name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SMTP 诊断与发件测试脚本")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="可选：读取 .env 路径（默认 ./.env）",
    )
    parser.add_argument("--host", default="", help="SMTP 主机（默认取 SMTP_HOST）")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="SMTP 端口（默认取 SMTP_PORT）",
    )
    parser.add_argument("--user", default="", help="SMTP 用户名（默认取 SMTP_USER）")
    parser.add_argument(
        "--password",
        default="",
        help="SMTP 密码（默认取 SMTP_PASSWORD）",
    )
    parser.add_argument("--from-addr", default="", help="发件人（默认取 SMTP_FROM）")
    parser.add_argument(
        "--to-addr",
        default="",
        help="收件人（默认取 DIGEST_EMAIL_TO 第一个）",
    )
    parser.add_argument("--starttls", action="store_true", help="强制启用 STARTTLS")
    parser.add_argument("--no-starttls", action="store_true", help="强制关闭 STARTTLS")
    parser.add_argument("--use-ssl", action="store_true", help="强制启用 SMTP_SSL")
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="连接/读超时秒数（默认 20）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只测到登录，不实际发送邮件")
    args = parser.parse_args()

    load_dotenv_if_exists(args.env_file)

    host = (args.host or get_env("SMTP_HOST", "")).strip()
    port = args.port or int(get_env("SMTP_PORT", "587") or "587")
    user = (args.user or get_env("SMTP_USER", "")).strip()
    password = args.password or get_env("SMTP_PASSWORD", "")
    from_addr = (args.from_addr or get_env("SMTP_FROM", "")).strip()
    default_to = get_env("DIGEST_EMAIL_TO", "").split(",")[0].strip()
    to_addr = (args.to_addr or default_to).strip()

    if args.starttls and args.no_starttls:
        print_fail("参数校验", "--starttls 与 --no-starttls 不能同时指定")
        return 2
    if args.use_ssl:
        starttls = False
    else:
        if args.starttls:
            starttls = True
        elif args.no_starttls:
            starttls = False
        else:
            starttls = (
                get_env("SMTP_STARTTLS", "true").strip().lower()
                in {"1", "true", "yes", "on"}
            )
    use_ssl = args.use_ssl or (
        get_env("SMTP_USE_SSL", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    try:
        require_non_empty("SMTP_HOST", host)
        require_non_empty("SMTP_FROM", from_addr)
        require_non_empty("DIGEST_EMAIL_TO / --to-addr", to_addr)
    except Exception as e:
        print_fail("配置检查", str(e))
        explain_common_causes("generic", e)
        return 2

    print("=== SMTP 诊断开始 ===")
    print(
        f"host={host} port={port} use_ssl={use_ssl} "
        f"starttls={starttls} timeout={args.timeout}s"
    )
    print(f"from={from_addr} to={to_addr}")
    print(f"auth_user={'<empty>' if not user else user}")
    print("")

    # 1) DNS
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        sample = infos[0][4][0] if infos else "unknown"
        print_ok("DNS 解析", f"{host} -> {sample} (共 {len(infos)} 条)")
    except Exception as e:
        print_fail("DNS 解析", f"{host}:{port}")
        explain_common_causes("dns", e)
        return 1

    # 2) TCP
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=args.timeout):
            pass
        dt = (time.perf_counter() - t0) * 1000
        print_ok("TCP 连接", f"{host}:{port} 连通，耗时 {dt:.0f}ms")
    except Exception as e:
        print_fail("TCP 连接", f"{host}:{port} 不可达")
        explain_common_causes("tcp", e)
        return 1

    # 3) SMTP 握手 / TLS / AUTH / SEND
    smtp: smtplib.SMTP | None = None
    try:
        if use_ssl:
            context = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(host, port, timeout=args.timeout, context=context)
            assert smtp is not None
            smtp.ehlo()
            print_ok("SMTP_SSL 握手", "SSL 通道已建立")
        else:
            smtp = smtplib.SMTP(host, port, timeout=args.timeout)
            assert smtp is not None
            smtp.ehlo()
            print_ok("SMTP 握手", "EHLO 成功")
            if starttls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
                smtp.ehlo()
                print_ok("STARTTLS", "升级到 TLS 成功")

        if user and password:
            smtp.login(user, password)
            print_ok("SMTP 登录", "AUTH 成功")
        elif user or password:
            print_fail("SMTP 登录", "只配置了 user 或 password 之一")
            explain_common_causes("auth", ValueError("user/password 需同时配置"))
            return 1
        else:
            print("[WARN] 跳过 SMTP 登录（未提供 user/password）")

        if args.dry_run:
            print_ok("DRY-RUN", "已验证到登录阶段，未发送邮件")
            return 0

        msg = EmailMessage()
        msg["Subject"] = "SMTP 诊断测试邮件"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(
            "这是一封 SMTP 诊断测试邮件。若收到说明链路已打通。",
            charset="utf-8",
        )
        smtp.send_message(msg)
        print_ok("发送邮件", "send_message 成功")
    except ssl.SSLError as e:
        print_fail("TLS 阶段", str(e))
        explain_common_causes("tls", e)
        return 1
    except smtplib.SMTPAuthenticationError as e:
        print_fail(
            "SMTP 认证",
            f"code={getattr(e, 'smtp_code', '?')} "
            f"{getattr(e, 'smtp_error', b'')!r}",
        )
        explain_common_causes("auth", e)
        return 1
    except smtplib.SMTPException as e:
        # 可能发生在 EHLO/STARTTLS/MAIL FROM/RCPT TO 等阶段
        print_fail("SMTP 协议阶段", str(e))
        explain_common_causes("send", e)
        return 1
    except (OSError, TimeoutError, socket.timeout) as e:
        print_fail("网络阶段", str(e))
        explain_common_causes("tcp", e)
        return 1
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass

    print("")
    print("=== 诊断完成：链路可用 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
