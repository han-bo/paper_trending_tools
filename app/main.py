from __future__ import annotations

import argparse
import sys

from loguru import logger

from app.config import settings
from app.llm.volcengine_client import chat_completions
from app.scheduler.jobs import run_daily_pipeline, setup_scheduler


def _run_test_llm() -> None:
    """发一条最短对话，验证 VOLCENGINE_* 与网络是否正常。"""
    if not settings.volcengine_api_key or not settings.volcengine_model:
        logger.error("未配置 VOLCENGINE_API_KEY 或 VOLCENGINE_MODEL，无法探测 LLM")
        sys.exit(1)
    try:
        text = chat_completions(
            [{"role": "user", "content": "请只回复两个字：通过"}],
            temperature=0.1,
        )
    except Exception as e:
        logger.exception("LLM 探测失败: {}", e)
        sys.exit(2)
    logger.info("LLM 探测成功，模型回复如下（首尾已去空白）:\n{}", text.strip())
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub + arXiv 个人研究情报 Agent（MVP）")
    parser.add_argument(
        "--once",
        action="store_true",
        help="立即执行一次抓取、排序、分析（若已配置）与推送",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="只发一条最短请求到火山方舟，验证 LLM 是否可用后退出",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    if args.test_llm:
        _run_test_llm()
        return

    if args.once:
        run_daily_pipeline()
        return

    sched = setup_scheduler()
    logger.info(
        "调度器已启动：每天 {:02d}:{:02d}（{}）",
        settings.scheduler_cron_hour,
        settings.scheduler_cron_minute,
        settings.scheduler_timezone,
    )
    sched.start()


if __name__ == "__main__":
    main()
