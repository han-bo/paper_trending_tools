"""应用配置：从环境变量读取，启动时可选加载项目根目录 `.env`（无额外依赖）。"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _load_env_file() -> None:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


_load_env_file()


def _env_str(key: str, default: str) -> str:
    v = os.environ.get(key)
    return default if v is None or v == "" else v


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Settings(BaseModel):
    github_token: str = Field(default="")
    github_search_query: str = Field(default="stars:>500")
    github_pushed_days: int = Field(default=7, ge=1, le=90)
    github_per_page: int = Field(default=20, ge=1, le=100)

    arxiv_rss_urls: str = Field(default="http://export.arxiv.org/rss/cs.AI")
    arxiv_max_entries: int = Field(default=30, ge=1, le=200)

    database_url: str = Field(default="sqlite:///data/local.db")

    volcengine_api_key: str = Field(default="")
    volcengine_api_base: str = Field(default="https://ark.cn-beijing.volces.com/api/v3")
    volcengine_model: str = Field(default="")

    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_starttls: bool = Field(default=True)
    smtp_use_ssl: bool = Field(default=False)
    digest_email_to: str = Field(default="")
    digest_email_subject: str = Field(default="【今日值得关注】研究摘要")

    digest_github_top_n: int = Field(default=5, ge=1, le=20)
    digest_arxiv_top_n: int = Field(default=3, ge=1, le=20)
    llm_analyze_github_top: int = Field(default=15, ge=1, le=50)
    llm_analyze_arxiv_top: int = Field(default=10, ge=1, le=50)

    scheduler_cron_hour: int = Field(default=8, ge=0, le=23)
    scheduler_cron_minute: int = Field(default=0, ge=0, le=59)
    scheduler_timezone: str = Field(default="Asia/Shanghai")

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            github_token=_env_str("GITHUB_TOKEN", ""),
            github_search_query=_env_str("GITHUB_SEARCH_QUERY", "stars:>500"),
            github_pushed_days=_env_int("GITHUB_PUSHED_DAYS", 7),
            github_per_page=_env_int("GITHUB_PER_PAGE", 20),
            arxiv_rss_urls=_env_str("ARXIV_RSS_URLS", "http://export.arxiv.org/rss/cs.AI"),
            arxiv_max_entries=_env_int("ARXIV_MAX_ENTRIES", 30),
            database_url=_env_str("DATABASE_URL", "sqlite:///data/local.db"),
            volcengine_api_key=_env_str("VOLCENGINE_API_KEY", ""),
            volcengine_api_base=_env_str(
                "VOLCENGINE_API_BASE",
                "https://ark.cn-beijing.volces.com/api/v3",
            ),
            volcengine_model=_env_str("VOLCENGINE_MODEL", ""),
            telegram_bot_token=_env_str("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=_env_str("TELEGRAM_CHAT_ID", ""),
            smtp_host=_env_str("SMTP_HOST", ""),
            smtp_port=_env_int("SMTP_PORT", 587),
            smtp_user=_env_str("SMTP_USER", ""),
            smtp_password=_env_str("SMTP_PASSWORD", ""),
            smtp_from=_env_str("SMTP_FROM", ""),
            smtp_starttls=_env_bool("SMTP_STARTTLS", True),
            smtp_use_ssl=_env_bool("SMTP_USE_SSL", False),
            digest_email_to=_env_str("DIGEST_EMAIL_TO", ""),
            digest_email_subject=_env_str("DIGEST_EMAIL_SUBJECT", "【今日值得关注】研究摘要"),
            digest_github_top_n=_env_int("DIGEST_GITHUB_TOP_N", 5),
            digest_arxiv_top_n=_env_int("DIGEST_ARXIV_TOP_N", 3),
            llm_analyze_github_top=_env_int("LLM_ANALYZE_GITHUB_TOP", 15),
            llm_analyze_arxiv_top=_env_int("LLM_ANALYZE_ARXIV_TOP", 10),
            scheduler_cron_hour=_env_int("SCHEDULER_CRON_HOUR", 8),
            scheduler_cron_minute=_env_int("SCHEDULER_CRON_MINUTE", 0),
            scheduler_timezone=_env_str("SCHEDULER_TIMEZONE", "Asia/Shanghai"),
        )


settings = Settings.load()
