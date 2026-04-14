import logging
import sys
import time
import traceback
from datetime import datetime, timedelta

from oa_crawler import config
from oa_crawler.crawler import OANotificationCrawler
from oa_crawler.db import (
    apply_crawler_runtime_config,
    create_crawl_job_log,
    get_existing_news_ids,
    initialize_schema,
    save_crawl_result,
    test_connection,
    update_crawl_job_log,
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_once() -> None:
    logger = logging.getLogger("oa_crawler")
    apply_crawler_runtime_config()
    logger.info("Single crawl task started")
    job_id = create_crawl_job_log(
        job_type="scheduled" if config.SCHEDULER_ENABLED else "manual",
        trigger_mode="scheduler" if config.SCHEDULER_ENABLED else "single",
        status="running",
        incremental_mode=int(config.INCREMENTAL_CRAWL_ENABLED),
        scheduler_enabled=config.SCHEDULER_ENABLED,
        interval_hours=None,
        message="Crawl task started",
    )
    crawler = OANotificationCrawler(existing_news_lookup=get_existing_news_ids)
    try:
        notifications, attachments = crawler.fetch_notifications()
        saved_notifications, saved_attachments, new_notifications = save_crawl_result(notifications, attachments)
        logger.info("MySQL save completed")
        logger.info("New notifications in current run: %s", len(new_notifications))
        update_crawl_job_log(
            job_id,
            status="success",
            notifications_count=len(notifications),
            attachments_count=len(attachments),
            db_notifications_count=saved_notifications,
            db_attachments_count=saved_attachments,
            message=(
                f"Crawl task completed successfully; "
                f"new_notifications={len(new_notifications)}"
            ),
        )
        print(f"notifications: {len(notifications)}")
        print(f"attachments: {len(attachments)}")
        print(f"db_notifications: {saved_notifications}")
        print(f"db_attachments: {saved_attachments}")
        print(f"new_notifications: {len(new_notifications)}")
    except KeyboardInterrupt:
        logger.warning("Program interrupted by user, saving partial results to MySQL")
        notifications = crawler.notifications
        attachments = crawler.attachments
        if notifications or attachments:
            saved_notifications, saved_attachments, new_notifications = save_crawl_result(notifications, attachments)
            logger.info("Partial MySQL save completed")
            logger.info("New notifications in interrupted run: %s", len(new_notifications))
            update_crawl_job_log(
                job_id,
                status="interrupted",
                notifications_count=len(notifications),
                attachments_count=len(attachments),
                db_notifications_count=saved_notifications,
                db_attachments_count=saved_attachments,
                message=(
                    f"Crawl task interrupted by user; partial data saved; "
                    f"new_notifications={len(new_notifications)}"
                ),
            )
            print(f"notifications: {len(notifications)}")
            print(f"attachments: {len(attachments)}")
            print(f"db_notifications: {saved_notifications}")
            print(f"db_attachments: {saved_attachments}")
            print(f"new_notifications: {len(new_notifications)}")
        else:
            logger.warning("No partial data available to save")
            update_crawl_job_log(
                job_id,
                status="interrupted",
                message="Crawl task interrupted by user; no partial data available",
            )
        raise
    except Exception as exc:
        update_crawl_job_log(
            job_id,
            status="failed",
            notifications_count=len(crawler.notifications),
            attachments_count=len(crawler.attachments),
            message="Crawl task failed",
            error_message="".join(traceback.format_exception(exc)),
        )
        raise


def run_scheduler() -> None:
    logger = logging.getLogger("oa_crawler")
    apply_crawler_runtime_config()
    interval_seconds = int(config.SCHEDULER_INTERVAL_MINUTES * 60)
    interval_display = f"{config.SCHEDULER_INTERVAL_MINUTES} minutes / {interval_seconds} seconds"
    logger.info(
        "Scheduler started: interval_minutes=%s, max_runs=%s",
        config.SCHEDULER_INTERVAL_MINUTES,
        config.SCHEDULER_MAX_RUNS,
    )
    print("=== Scheduler Started ===")
    print(f"scheduler_enabled: {config.SCHEDULER_ENABLED}")
    print(f"scheduler_interval: {interval_display}")
    print(f"scheduler_max_runs: {config.SCHEDULER_MAX_RUNS}")
    print(f"max_records: {config.MAX_RECORDS}")
    print(f"request_delay_range: {config.REQUEST_DELAY_MIN} - {config.REQUEST_DELAY_MAX} seconds")
    scheduler_job_id = create_crawl_job_log(
        job_type="scheduler_boot",
        trigger_mode="scheduler",
        status="success",
        incremental_mode=int(config.INCREMENTAL_CRAWL_ENABLED),
        scheduler_enabled=config.SCHEDULER_ENABLED,
        interval_hours=None,
        message="Scheduler started successfully",
    )
    update_crawl_job_log(
        scheduler_job_id,
        status="success",
        message="Scheduler boot record created successfully",
    )
    run_count = 0
    while True:
        if config.SCHEDULER_MAX_RUNS > 0 and run_count >= config.SCHEDULER_MAX_RUNS:
            logger.info("Scheduler finished planned runs: total_runs=%s", run_count)
            print(f"scheduler_finished: total_runs={run_count}")
            break
        cycle_start = time.time()
        current_round = run_count + 1
        round_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("========================================")
        print(f"scheduler_round_start: round={current_round}")
        print(f"scheduler_round_started_at: {round_started_at}")
        print(f"scheduler_round_config_enabled: {config.SCHEDULER_ENABLED}")
        print(f"scheduler_round_config_interval_minutes: {config.SCHEDULER_INTERVAL_MINUTES}")
        print(f"scheduler_round_config_interval_seconds: {interval_seconds}")
        print(f"scheduler_round_config_max_runs: {config.SCHEDULER_MAX_RUNS}")
        print(f"scheduler_round_config_max_records: {config.MAX_RECORDS}")
        print(
            "scheduler_round_config_request_delay_seconds: "
            f"{config.REQUEST_DELAY_MIN} - {config.REQUEST_DELAY_MAX}"
        )
        print("========================================")
        try:
            run_once()
            run_count += 1
            print(f"scheduler_round_result: round={current_round}, status=success")
        except KeyboardInterrupt:
            logger.warning("Scheduler interrupted by user")
            print("scheduler_interrupted: by user")
            raise
        except Exception:
            logger.exception("Scheduled crawl task failed")
            run_count += 1
            print(f"scheduler_round_result: round={current_round}, status=failed")

        elapsed = int(time.time() - cycle_start)
        sleep_seconds = max(interval_seconds - elapsed, 0)
        if config.SCHEDULER_MAX_RUNS > 0 and run_count >= config.SCHEDULER_MAX_RUNS:
            logger.info("Scheduler finished planned runs after current cycle: total_runs=%s", run_count)
            print(f"scheduler_finished_after_cycle: total_runs={run_count}")
            break
        next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
        logger.info("Next scheduled run in %s seconds", sleep_seconds)
        print("--------------- Scheduler Wait ---------------")
        print(f"scheduler_next_run_in_seconds: {sleep_seconds}")
        print(f"scheduler_next_run_at: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("------------------------------------------------")
        time.sleep(sleep_seconds)


def main() -> None:
    setup_logging()
    logger = logging.getLogger("oa_crawler")
    logger.info("Program started")
    initialize_schema()
    test_connection()
    apply_crawler_runtime_config()
    try:
        if config.SCHEDULER_ENABLED:
            run_scheduler()
        else:
            run_once()
    except Exception:
        logger.exception("Program failed")
        raise


if __name__ == "__main__":
    main()
