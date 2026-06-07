from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from loguru import logger

from app.config import settings
from app.db.session import get_session, init_db
from app.feedback.links import item_type_from_code, verify_signature
from app.feedback.report import error_html, render_confirm_page
from app.feedback.storage import record_feedback


class FeedbackHandler(BaseHTTPRequestHandler):
    server_version = "PaperTrendingFeedback/1.0"

    def log_message(self, fmt: str, *args) -> None:
        logger.info("feedback {} - " + fmt, self.address_string(), *args)

    def _send_html(self, status: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "f" or parts[1] not in ("up", "down"):
            self._send_html(404, error_html("页面不存在"))
            return

        signal = parts[1]
        qs = parse_qs(parsed.query)
        type_code = (qs.get("t") or [""])[0]
        item_key = (qs.get("k") or [""])[0]
        digest_date = (qs.get("d") or [""])[0]
        sig = (qs.get("sig") or [""])[0]

        if not type_code or not item_key or not digest_date or not sig:
            self._send_html(400, error_html("链接参数不完整"))
            return

        try:
            item_type = item_type_from_code(type_code)
        except ValueError:
            self._send_html(400, error_html("无效的条目类型"))
            return

        if not verify_signature(
            item_type=item_type,
            item_key=item_key,
            digest_date=digest_date,
            signal=signal,
            sig=sig,
        ):
            self._send_html(403, error_html("链接无效或已过期"))
            return

        session = get_session()
        try:
            record_feedback(
                session,
                item_type=item_type,
                item_key=item_key,
                digest_date=digest_date,
                signal=signal,
            )
        finally:
            session.close()

        page = render_confirm_page(
            signal=signal,
            item_type=item_type,
            item_key=item_key,
            digest_date=digest_date,
        )
        self._send_html(200, page)


def run_feedback_server() -> None:
    if not settings.feedback_base_url.strip() or not settings.feedback_hmac_secret.strip():
        raise RuntimeError("请配置 FEEDBACK_BASE_URL 与 FEEDBACK_HMAC_SECRET")
    init_db()
    host = settings.feedback_listen_host
    port = settings.feedback_listen_port
    server = HTTPServer((host, port), FeedbackHandler)
    logger.info("反馈服务已启动：http://{}:{}", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("反馈服务已停止")
        server.server_close()
