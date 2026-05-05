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


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


class Settings(BaseModel):
    github_token: str = Field(default="")
    # 建议偏「趋势发现」：避免常年顶流占榜；可用 .env 覆盖为你自己的 query
    github_search_query: str = Field(default="stars:50..5000")
    github_pushed_days: int = Field(default=7, ge=1, le=90)
    github_created_days: int = Field(default=30, ge=1, le=365)
    github_max_stars: int = Field(default=50000, ge=100, le=5000000)
    github_per_page: int = Field(default=20, ge=1, le=100)

    arxiv_rss_urls: str = Field(default="http://export.arxiv.org/rss/cs.AI")
    arxiv_max_entries: int = Field(default=30, ge=1, le=200)
    # arXiv 要求可识别的 User-Agent，见 https://info.arxiv.org/help/api/user-manual.html
    arxiv_http_user_agent: str = Field(
        default=(
            "paper_trending_tools/1.0 "
            "(+https://info.arxiv.org/help/api/user-manual.html)"
        )
    )

    database_url: str = Field(default="sqlite:///data/local.db")

    volcengine_api_key: str = Field(default="")
    volcengine_api_base: str = Field(default="https://ark.cn-beijing.volces.com/api/v3")
    volcengine_model: str = Field(default="")
    volcengine_connect_timeout: float = Field(default=30.0, ge=5.0, le=120.0)
    volcengine_read_timeout: float = Field(default=300.0, ge=30.0, le=900.0)
    llm_github_readme_max_chars: int = Field(default=6000, ge=2000, le=50000)
    llm_paper_abstract_max_chars: int = Field(default=8000, ge=1000, le=50000)
    volcengine_429_max_attempts: int = Field(default=8, ge=2, le=20)
    volcengine_429_base_wait_seconds: float = Field(default=2.0, ge=0.5, le=60.0)
    volcengine_llm_interval_seconds: float = Field(default=1.5, ge=0.0, le=60.0)

    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    digest_email_to: str = Field(default="")
    digest_email_subject: str = Field(default="【今日值得关注】研究摘要")

    zoho_accounts_base: str = Field(default="")
    zoho_mail_api_base: str = Field(default="")
    zoho_oauth_client_id: str = Field(default="")
    zoho_oauth_client_secret: str = Field(default="")
    zoho_oauth_refresh_token: str = Field(default="")
    zoho_mail_from: str = Field(default="")
    zoho_mail_account_id: str = Field(default="")

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
            github_search_query=_env_str("GITHUB_SEARCH_QUERY", "stars:50..5000"),
            github_pushed_days=_env_int("GITHUB_PUSHED_DAYS", 7),
            github_created_days=_env_int("GITHUB_CREATED_DAYS", 30),
            github_max_stars=_env_int("GITHUB_MAX_STARS", 50000),
            github_per_page=_env_int("GITHUB_PER_PAGE", 20),
            arxiv_rss_urls=_env_str("ARXIV_RSS_URLS", "http://export.arxiv.org/rss/cs.AI"),
            arxiv_max_entries=_env_int("ARXIV_MAX_ENTRIES", 30),
            arxiv_http_user_agent=_env_str(
                "ARXIV_HTTP_USER_AGENT",
                "paper_trending_tools/1.0 (+https://info.arxiv.org/help/api/user-manual.html)",
            ),
            database_url=_env_str("DATABASE_URL", "sqlite:///data/local.db"),
            volcengine_api_key=_env_str("VOLCENGINE_API_KEY", ""),
            volcengine_api_base=_env_str(
                "VOLCENGINE_API_BASE",
                "https://ark.cn-beijing.volces.com/api/v3",
            ),
            volcengine_model=_env_str("VOLCENGINE_MODEL", ""),
            volcengine_connect_timeout=_env_float("VOLCENGINE_CONNECT_TIMEOUT", 30.0),
            volcengine_read_timeout=_env_float("VOLCENGINE_READ_TIMEOUT", 300.0),
            llm_github_readme_max_chars=_env_int("LLM_GITHUB_README_MAX_CHARS", 6000),
            llm_paper_abstract_max_chars=_env_int("LLM_PAPER_ABSTRACT_MAX_CHARS", 8000),
            volcengine_429_max_attempts=_env_int("VOLCENGINE_429_MAX_ATTEMPTS", 8),
            volcengine_429_base_wait_seconds=_env_float(
                "VOLCENGINE_429_BASE_WAIT_SECONDS",
                2.0,
            ),
            volcengine_llm_interval_seconds=_env_float(
                "VOLCENGINE_LLM_INTERVAL_SECONDS",
                1.5,
            ),
            telegram_bot_token=_env_str("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=_env_str("TELEGRAM_CHAT_ID", ""),
            digest_email_to=_env_str("DIGEST_EMAIL_TO", ""),
            digest_email_subject=_env_str("DIGEST_EMAIL_SUBJECT", "【今日值得关注】研究摘要"),
            zoho_accounts_base=_env_str("ZOHO_ACCOUNTS_BASE", ""),
            zoho_mail_api_base=_env_str("ZOHO_MAIL_API_BASE", ""),
            zoho_oauth_client_id=_env_str("ZOHO_OAUTH_CLIENT_ID", ""),
            zoho_oauth_client_secret=_env_str("ZOHO_OAUTH_CLIENT_SECRET", ""),
            zoho_oauth_refresh_token=_env_str("ZOHO_OAUTH_REFRESH_TOKEN", ""),
            zoho_mail_from=_env_str("ZOHO_MAIL_FROM", ""),
            zoho_mail_account_id=_env_str("ZOHO_MAIL_ACCOUNT_ID", ""),
            digest_github_top_n=_env_int("DIGEST_GITHUB_TOP_N", 5),
            digest_arxiv_top_n=_env_int("DIGEST_ARXIV_TOP_N", 3),
            llm_analyze_github_top=_env_int("LLM_ANALYZE_GITHUB_TOP", 15),
            llm_analyze_arxiv_top=_env_int("LLM_ANALYZE_ARXIV_TOP", 10),
            scheduler_cron_hour=_env_int("SCHEDULER_CRON_HOUR", 8),
            scheduler_cron_minute=_env_int("SCHEDULER_CRON_MINUTE", 0),
            scheduler_timezone=_env_str("SCHEDULER_TIMEZONE", "Asia/Shanghai"),
        )


settings = Settings.load()
