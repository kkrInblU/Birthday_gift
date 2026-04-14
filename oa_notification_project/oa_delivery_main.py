import logging
import sys

from oa_crawler import config
from oa_crawler.db import (
    create_crawl_job_log,
    initialize_schema,
    test_connection,
    update_crawl_job_log,
)
from oa_crawler.delivery import (
    prepare_due_user_delivery_queue,
    send_pending_email_deliveries,
    send_pending_miniapp_deliveries,
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_delivery_job(*, trigger_mode: str = "single") -> dict:
    logger = logging.getLogger("oa_crawler")
    job_id = None
    try:
        logger.info("User-based notification delivery task started")
        initialize_schema()
        test_connection()

        job_id = create_crawl_job_log(
            job_type="delivery_only",
            trigger_mode=trigger_mode,
            status="running",
            incremental_mode=int(config.INCREMENTAL_CRAWL_ENABLED),
            scheduler_enabled=False,
            interval_hours=None,
            message="User-based notification delivery task started",
        )

        queue_summary = prepare_due_user_delivery_queue(job_id=job_id)
        # Send all current pending deliveries so historical pending rows do not block
        # newly unified email/miniapp delivery in the same cycle.
        email_success_count, email_failed_count = send_pending_email_deliveries()
        miniapp_success_count, miniapp_failed_count = send_pending_miniapp_deliveries()
        total_success_count = email_success_count + miniapp_success_count
        total_failed_count = email_failed_count + miniapp_failed_count
        update_crawl_job_log(
            job_id,
            status="success" if total_failed_count == 0 else "partial_success",
            notifications_count=queue_summary["notifications_matched"],
            db_notifications_count=queue_summary["email_records_created"],
            db_attachments_count=queue_summary["miniapp_records_created"],
            message=(
                "Delivery task completed; "
                f"checked_users={queue_summary['checked_users']}; "
                f"matched_notifications={queue_summary['notifications_matched']}; "
                f"email_records={queue_summary['email_records_created']}; "
                f"miniapp_records={queue_summary['miniapp_records_created']}; "
                f"email_delivered={email_success_count}; "
                f"email_failed={email_failed_count}; "
                f"miniapp_delivered={miniapp_success_count}; "
                f"miniapp_failed={miniapp_failed_count}"
            ),
        )
        print(f"checked_users: {queue_summary['checked_users']}")
        print(f"matched_notifications: {queue_summary['notifications_matched']}")
        print(f"created_email_delivery_records: {queue_summary['email_records_created']}")
        print(f"created_miniapp_delivery_records: {queue_summary['miniapp_records_created']}")
        print(f"successful_email_deliveries: {email_success_count}")
        print(f"failed_email_deliveries: {email_failed_count}")
        print(f"successful_miniapp_deliveries: {miniapp_success_count}")
        print(f"failed_miniapp_deliveries: {miniapp_failed_count}")
        print(f"successful_deliveries: {total_success_count}")
        print(f"failed_deliveries: {total_failed_count}")
        return {
            "jobId": job_id,
            "checkedUsers": queue_summary["checked_users"],
            "matchedNotifications": queue_summary["notifications_matched"],
            "createdEmailDeliveryRecords": queue_summary["email_records_created"],
            "createdMiniappDeliveryRecords": queue_summary["miniapp_records_created"],
            "successfulEmailDeliveries": email_success_count,
            "failedEmailDeliveries": email_failed_count,
            "successfulMiniappDeliveries": miniapp_success_count,
            "failedMiniappDeliveries": miniapp_failed_count,
            "successfulDeliveries": total_success_count,
            "failedDeliveries": total_failed_count,
        }
    except Exception as exc:
        if job_id is not None:
            update_crawl_job_log(
                job_id,
                status="failed",
                message="User-based notification delivery task failed",
                error_message=str(exc),
            )
        logger.exception("User-based notification delivery task failed")
        raise


def main() -> None:
    setup_logging()
    run_delivery_job(trigger_mode="single")


if __name__ == "__main__":
    main()
