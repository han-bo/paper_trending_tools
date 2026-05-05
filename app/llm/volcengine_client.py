from __future__ import annotations

import random
import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings


def _wait_after_429(response: httpx.Response, attempt_index: int) -> float:
    """429 后等待秒数：优先 Retry-After，否则指数退避 + 少量抖动。"""
    ra = response.headers.get("Retry-After")
    if ra:
        try:
            return min(float(ra), 120.0)
        except ValueError:
            pass
    base = settings.volcengine_429_base_wait_seconds
    raw = base * (2**attempt_index) + random.uniform(0.0, 0.75)
    return min(raw, 90.0)


def chat_completions(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
) -> str:
    """调用火山引擎方舟 OpenAI 兼容 Chat Completions（仅用 httpx，无额外 SDK）。"""
    if not settings.volcengine_api_key or not settings.volcengine_model:
        raise RuntimeError("未配置 VOLCENGINE_API_KEY 或 VOLCENGINE_MODEL（接入点 ID）")
    url = f"{settings.volcengine_api_base.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.volcengine_model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.volcengine_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=settings.volcengine_connect_timeout,
        read=settings.volcengine_read_timeout,
        write=60.0,
        pool=30.0,
    )
    max_attempts = settings.volcengine_429_max_attempts
    with httpx.Client(timeout=timeout) as client:
        r: httpx.Response | None = None
        for attempt in range(max_attempts):
            r = client.post(url, json=payload, headers=headers)
            if r.status_code == 429:
                if attempt >= max_attempts - 1:
                    break
                w = _wait_after_429(r, attempt)
                logger.warning(
                    "方舟 API 429，{:.1f}s 后重试（第 {}/{} 次请求）",
                    w,
                    attempt + 2,
                    max_attempts,
                )
                time.sleep(w)
                continue
            break
        assert r is not None
        if r.status_code >= 400:
            logger.error("火山引擎 API 错误 {}: {}", r.status_code, r.text[:500])
        r.raise_for_status()
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        logger.error("解析 LLM 响应失败: {}", data)
        raise RuntimeError("LLM 响应格式异常") from e
