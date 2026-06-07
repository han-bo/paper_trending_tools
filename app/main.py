from __future__ import annotations

import argparse
import sys

from loguru import logger

from app.config import settings
from app.inspect_db import inspect_database
from app.llm.volcengine_client import chat_completions
from app.scheduler.jobs import run_daily_pipeline, setup_scheduler
from app.feedback.report import run_feedback_report
from app.feedback.server import run_feedback_server


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
    parser.add_argument(
        "--inspect-db",
        action="store_true",
        help="打印库里抓取的 GitHub / arXiv / 每日摘要（只读，不跑任务）",
    )
    parser.add_argument(
        "--inspect-limit",
        type=int,
        default=20,
        help="与 --inspect-db 合用：GitHub、arXiv 各显示最近几条（默认 20）",
    )
    parser.add_argument(
        "--digest-limit",
        type=int,
        default=5,
        help="与 --inspect-db 合用：daily_digest 显示几条（默认 5）",
    )
    parser.add_argument(
        "--feedback-report",
        action="store_true",
        help="打印近 N 天用户反馈周报（只读）",
    )
    parser.add_argument(
        "--feedback-days",
        type=int,
        default=7,
        help="与 --feedback-report 合用：统计最近几天（默认 7）",
    )
    parser.add_argument(
        "--email-report",
        action="store_true",
        help="与 --feedback-report 合用：将周报发到 DIGEST_EMAIL_TO",
    )
    parser.add_argument(
        "--run-feedback-server",
        action="store_true",
        help="启动邮件反馈 HTTP 服务（供 nginx 反代）",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    if args.test_llm:
        _run_test_llm()
        return

    if args.inspect_db:
        if args.inspect_limit < 1 or args.digest_limit < 1:
            logger.error("--inspect-limit / --digest-limit 须 >= 1")
            sys.exit(1)
        inspect_database(limit=args.inspect_limit, digest_limit=args.digest_limit)
        return

    if args.feedback_report:
        if args.feedback_days < 1:
            logger.error("--feedback-days 须 >= 1")
            sys.exit(1)
        report = run_feedback_report(days=args.feedback_days, email=args.email_report)
        print(report)
        return

    if args.run_feedback_server:
        run_feedback_server()
        return

    if args.once:
        run_daily_pipeline()
        return

    sched = setup_scheduler()
    logger.info(
        "调度器已启动：每天 {:02d}:{:02d}（{}）跑 digest；"
        "每周 {} {:02d}:{:02d} 发反馈周报",
        settings.scheduler_cron_hour,
        settings.scheduler_cron_minute,
        settings.scheduler_timezone,
        settings.feedback_report_dow,
        settings.feedback_report_hour,
        settings.feedback_report_minute,
    )
    sched.start()


if __name__ == "__main__":
    main()
