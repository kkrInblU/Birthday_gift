import uuid
from datetime import datetime

import pymysql


DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "1234",
    "database": "oa_notifications",
    "charset": "utf8mb4",
}

TEST_USER_EMAIL = "3307180168@qq.com"
SUBSCRIPTION_ID_FOR_DEMO = 84
UNSUBSCRIBED_DEPARTMENT = "UNSUB_DEPT_TEST"


def main() -> None:
    subscribed_news_id = f"TEST_SUB_{uuid.uuid4().hex[:10]}"
    unsubscribed_news_id = f"TEST_UNSUB_{uuid.uuid4().hex[:10]}"

    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT target_value FROM subscriptions WHERE id = %s",
            (SUBSCRIPTION_ID_FOR_DEMO,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("subscription demo target not found")

        subscribed_department = row[0]
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            UPDATE users
            SET last_notification_check_at = DATE_SUB(NOW(), INTERVAL 70 MINUTE)
            WHERE email = %s
            """,
            (TEST_USER_EMAIL,),
        )

        insert_sql = """
        INSERT INTO notifications (
            news_id,
            title,
            category,
            fragment_id,
            publish_time,
            publish_department,
            content_html,
            content_text,
            detail_url,
            view_count,
            first_seen_time,
            last_seen_time,
            crawl_time
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        cursor.execute(
            insert_sql,
            (
                subscribed_news_id,
                "TEST subscribed notification",
                "test",
                "test_fragment",
                now_text,
                subscribed_department,
                "<p>test subscribed notification</p>",
                "test subscribed notification",
                f"https://example.com/{subscribed_news_id}",
                0,
                now_text,
                now_text,
                now_text,
            ),
        )

        cursor.execute(
            insert_sql,
            (
                unsubscribed_news_id,
                "TEST unsubscribed notification",
                "test",
                "test_fragment",
                now_text,
                UNSUBSCRIBED_DEPARTMENT,
                "<p>test unsubscribed notification</p>",
                "test unsubscribed notification",
                f"https://example.com/{unsubscribed_news_id}",
                0,
                now_text,
                now_text,
                now_text,
            ),
        )

    conn.commit()
    conn.close()

    print("created subscribed notification:", subscribed_news_id)
    print("created unsubscribed notification:", unsubscribed_news_id)
    print("subscribed department:", subscribed_department)
    print("unsubscribed department:", UNSUBSCRIBED_DEPARTMENT)


if __name__ == "__main__":
    main()
