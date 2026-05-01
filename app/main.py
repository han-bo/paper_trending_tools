from __future__ import annotations

import argparse
import sys

from loguru import logger

from app.config import settings
from app.scheduler.jobs import run_daily_pipeline, setup_scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub + arXiv 个人研究情报 Agent（MVP）")
    parser.add_argument(
        "--once",
        action="store_true",
        help="立即执行一次抓取、排序、分析（若已配置）与推送",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO")

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
