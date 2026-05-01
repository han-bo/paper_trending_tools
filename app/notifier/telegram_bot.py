from __future__ import annotations

import asyncio

from loguru import logger
from telegram import Bot

from app.config import settings


def _chat_id() -> int | str:
    s = settings.telegram_chat_id.strip()
    if not s:
        raise RuntimeError("未配置 TELEGRAM_CHAT_ID")
    try:
        return int(s)
    except ValueError:
        return s


def _chunk_text(text: str, limit: int = 4000) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
    n = 0
    for line in text.splitlines(keepends=True):
        if n + len(line) > limit and buf:
            parts.append("".join(buf))
            buf = []
            n = 0
        buf.append(line)
        n += len(line)
    if buf:
        parts.append("".join(buf))
    return parts


async def send_digest_async(content: str) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("未配置 TELEGRAM_BOT_TOKEN")
    bot = Bot(settings.telegram_bot_token)
    chat = _chat_id()
    chunks = _chunk_text(content)
    for chunk in chunks:
        await bot.send_message(chat_id=chat, text=chunk, disable_web_page_preview=True)
    logger.info("Telegram 推送完成，共 {} 条消息", len(chunks))


def send_digest(content: str) -> None:
    asyncio.run(send_digest_async(content))
