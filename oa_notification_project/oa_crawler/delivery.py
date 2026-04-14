import logging
from collections import defaultdict

from oa_crawler.db import (
    count_user_new_notifications_since,
    create_email_delivery_records,
    create_due_delivery_records_for_user,
    get_due_users_for_notification_check,
    get_oldest_notifications,
    get_pending_email_deliveries,
    get_pending_miniapp_deliveries,
    mark_delivery_failed,
    mark_delivery_success,
    update_user_last_notification_check_at,
)
from oa_crawler.mailer import send_notifications_email
from oa_crawler.miniapp_notifier import MiniappNotifierError, miniapp_is_configured, send_subscribe_message


LOGGER = logging.getLogger("oa_crawler")


def enqueue_oldest_notifications_for_email(*, limit: int = 3, job_id: int | None = None) -> tuple[list[dict], int]:
    notifications = get_oldest_notifications(limit=limit)
    if not notifications:
        LOGGER.info("No notifications found in database for delivery")
        return [], 0

    created_count = create_email_delivery_records(notifications, job_id=job_id)
    LOGGER.info(
        "Existing notification delivery queue prepared: notifications=%s, delivery_records=%s",
        len(notifications),
        created_count,
    )
    return notifications, created_count


def send_pending_email_deliveries(*, job_id: int | None = None) -> tuple[int, int]:
    pending_rows = get_pending_email_deliveries(job_id=job_id)
    if not pending_rows:
        LOGGER.info("No pending email deliveries found")
        return 0, 0

    grouped_rows: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in pending_rows:
        grouped_rows[(row["user_id"], row["recipient"])].append(row)

    success_count = 0
    failed_count = 0
    for (_, recipient), rows in grouped_rows.items():
        delivery_ids = [int(item["delivery_id"]) for item in rows]
        notifications = [
            {
                "news_id": item["news_id"],
                "title": item["title"],
                "category": item["category"],
                "fragment_id": item["fragment_id"],
                "publish_time": item["publish_time"],
                "publish_department": item["publish_department"],
                "detail_url": item["detail_url"],
                "content_text": item["content_text"],
            }
            for item in rows
        ]
        try:
            send_notifications_email(recipient, notifications)
            mark_delivery_success(delivery_ids)
            success_count += len(delivery_ids)
        except Exception as exc:
            LOGGER.exception("Email delivery failed: recipient=%s", recipient)
            mark_delivery_failed(delivery_ids, str(exc))
            failed_count += len(delivery_ids)

    LOGGER.info(
        "Pending email deliveries processed: success=%s, failed=%s",
        success_count,
        failed_count,
    )
    return success_count, failed_count


def send_pending_miniapp_deliveries(*, job_id: int | None = None) -> tuple[int, int]:
    pending_rows = get_pending_miniapp_deliveries(job_id=job_id)
    if not pending_rows:
        LOGGER.info("No pending miniapp deliveries found")
        return 0, 0

    if not miniapp_is_configured():
        error_message = "miniapp notifier not configured"
        delivery_ids = [int(item["delivery_id"]) for item in pending_rows]
        mark_delivery_failed(delivery_ids, error_message)
        LOGGER.warning("Miniapp deliveries marked failed because miniapp config is incomplete")
        return 0, len(delivery_ids)

    success_count = 0
    failed_count = 0
    for row in pending_rows:
        delivery_id = int(row["delivery_id"])
        openid = str(row.get("wechat_openid") or "").strip()
        if not openid:
            mark_delivery_failed([delivery_id], "user wechat_openid not bound")
            failed_count += 1
            continue

        notification = {
            "news_id": row["news_id"],
            "title": row["title"],
            "category": row["category"],
            "fragment_id": row["fragment_id"],
            "publish_time": row["publish_time"],
            "publish_department": row["publish_department"],
            "detail_url": row["detail_url"],
            "content_text": row["content_text"],
        }
        try:
            response = send_subscribe_message(
                openid,
                notification,
                page=f"pages/detail/detail?newsId={row['news_id']}",
            )
            mark_delivery_success([delivery_id], provider_message_id=str(response.get("msgid") or ""))
            success_count += 1
        except MiniappNotifierError as exc:
            LOGGER.exception("Miniapp delivery failed: delivery_id=%s, user_id=%s", delivery_id, row["user_id"])
            mark_delivery_failed([delivery_id], str(exc))
            failed_count += 1

    LOGGER.info(
        "Pending miniapp deliveries processed: success=%s, failed=%s",
        success_count,
        failed_count,
    )
    return success_count, failed_count


def prepare_due_user_delivery_queue(*, job_id: int | None = None) -> dict:
    due_users = get_due_users_for_notification_check()
    if not due_users:
        LOGGER.info("No due users found for notification delivery check")
        return {
            "checked_users": 0,
            "notifications_matched": 0,
            "email_records_created": 0,
            "miniapp_records_created": 0,
        }

    checked_users = 0
    notifications_matched = 0
    email_records_created = 0
    miniapp_records_created = 0

    for user in due_users:
        user_id = int(user["id"])
        since_time = user.get("last_notification_check_at") or user.get("created_at")
        notifications_count = count_user_new_notifications_since(user_id, since_time)
        created = create_due_delivery_records_for_user(user_id, since_time, job_id=job_id)
        update_user_last_notification_check_at(user_id)

        checked_users += 1
        notifications_matched += notifications_count
        email_records_created += int(created["email_created"])
        miniapp_records_created += int(created["miniapp_created"])

        LOGGER.info(
            "User delivery check finished: user_id=%s, interval_minutes=%s, notifications=%s, email_records=%s, miniapp_records=%s",
            user_id,
            user.get("notification_refresh_interval_minutes"),
            notifications_count,
            created["email_created"],
            created["miniapp_created"],
        )

    summary = {
        "checked_users": checked_users,
        "notifications_matched": notifications_matched,
        "email_records_created": email_records_created,
        "miniapp_records_created": miniapp_records_created,
    }
    LOGGER.info("Due user delivery queue prepared: %s", summary)
    return summary
