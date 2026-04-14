import json
import logging
from contextlib import closing
from datetime import datetime

try:
    import pymysql
    from pymysql.connections import Connection
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency 'pymysql'. Install it with: pip install pymysql"
    ) from exc

from oa_crawler import config


LOGGER = logging.getLogger("oa_crawler")


AUDIENCE_TYPES = ("undergraduate", "graduate", "staff")
AUDIENCE_SCORE_THRESHOLD = 5
AUDIENCE_FIELD_CONFIG = {
    "undergraduate": {
        "flag": "audience_undergraduate",
        "version": "audience_undergraduate_rule_version",
        "detail": "audience_undergraduate_rule_detail",
    },
    "graduate": {
        "flag": "audience_graduate",
        "version": "audience_graduate_rule_version",
        "detail": "audience_graduate_rule_detail",
    },
    "staff": {
        "flag": "audience_staff",
        "version": "audience_staff_rule_version",
        "detail": "audience_staff_rule_detail",
    },
}


NOTIFICATIONS_DDL = """
CREATE TABLE IF NOT EXISTS notifications (
    id INT NOT NULL AUTO_INCREMENT,
    news_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(50) DEFAULT NULL,
    fragment_id VARCHAR(64) DEFAULT NULL,
    publish_time DATETIME DEFAULT NULL,
    publish_department VARCHAR(100) DEFAULT NULL,
    content_html LONGTEXT,
    content_text LONGTEXT,
    detail_url VARCHAR(500) DEFAULT NULL,
    audience_undergraduate TINYINT NOT NULL DEFAULT 0,
    audience_undergraduate_rule_version VARCHAR(20) DEFAULT NULL,
    audience_undergraduate_rule_detail LONGTEXT,
    audience_graduate TINYINT NOT NULL DEFAULT 0,
    audience_graduate_rule_version VARCHAR(20) DEFAULT NULL,
    audience_graduate_rule_detail LONGTEXT,
    audience_staff TINYINT NOT NULL DEFAULT 0,
    audience_staff_rule_version VARCHAR(20) DEFAULT NULL,
    audience_staff_rule_detail LONGTEXT,
    view_count INT NOT NULL DEFAULT 0,
    first_seen_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    crawl_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_notifications_news_id (news_id),
    KEY idx_notifications_title (title),
    KEY idx_notifications_publish_time (publish_time),
    KEY idx_notifications_publish_department (publish_department),
    FULLTEXT KEY ftx_notifications_content_text (content_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

AUDIENCE_KEYWORD_RULES_DDL = """
CREATE TABLE IF NOT EXISTS audience_keyword_rules (
    id BIGINT NOT NULL AUTO_INCREMENT,
    audience_type VARCHAR(32) NOT NULL,
    rule_scope VARCHAR(32) NOT NULL,
    keyword VARCHAR(100) NOT NULL,
    weight INT NOT NULL DEFAULT 1,
    status TINYINT NOT NULL DEFAULT 1,
    rule_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_audience_keyword_rule (audience_type, rule_scope, keyword, rule_version),
    KEY idx_audience_keyword_status (audience_type, status),
    KEY idx_audience_keyword_scope (rule_scope)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

AUDIENCE_DEPARTMENT_RULES_DDL = """
CREATE TABLE IF NOT EXISTS audience_department_rules (
    id BIGINT NOT NULL AUTO_INCREMENT,
    audience_type VARCHAR(32) NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    weight INT NOT NULL DEFAULT 1,
    status TINYINT NOT NULL DEFAULT 1,
    rule_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_audience_department_rule (audience_type, department_name, rule_version),
    KEY idx_audience_department_status (audience_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

ATTACHMENTS_DDL = """
CREATE TABLE IF NOT EXISTS attachments (
    id INT NOT NULL AUTO_INCREMENT,
    news_id VARCHAR(64) NOT NULL,
    file_id VARCHAR(100) NOT NULL,
    filename VARCHAR(255) DEFAULT NULL,
    extension VARCHAR(20) DEFAULT NULL,
    size BIGINT DEFAULT NULL,
    crawl_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_attachments_news_file (news_id, file_id),
    KEY idx_attachments_news_id (news_id),
    CONSTRAINT fk_attachments_news_id
        FOREIGN KEY (news_id) REFERENCES notifications (news_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CRAWL_JOB_LOG_DDL = """
CREATE TABLE IF NOT EXISTS crawl_job_log (
    id BIGINT NOT NULL AUTO_INCREMENT,
    job_type VARCHAR(32) NOT NULL DEFAULT 'manual',
    trigger_mode VARCHAR(32) NOT NULL DEFAULT 'single',
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    incremental_mode TINYINT NOT NULL DEFAULT 0,
    scheduler_enabled TINYINT NOT NULL DEFAULT 0,
    interval_hours INT DEFAULT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME DEFAULT NULL,
    duration_seconds INT DEFAULT NULL,
    notifications_count INT NOT NULL DEFAULT 0,
    attachments_count INT NOT NULL DEFAULT 0,
    db_notifications_count INT NOT NULL DEFAULT 0,
    db_attachments_count INT NOT NULL DEFAULT 0,
    message TEXT,
    error_message LONGTEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_crawl_job_log_started_at (started_at),
    KEY idx_crawl_job_log_status (status),
    KEY idx_crawl_job_log_job_type (job_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CRAWLER_RUNTIME_CONFIG_DDL = """
CREATE TABLE IF NOT EXISTS crawler_runtime_config (
    config_key VARCHAR(64) NOT NULL,
    config_value VARCHAR(255) NOT NULL,
    config_type VARCHAR(32) NOT NULL DEFAULT 'string',
    description VARCHAR(255) DEFAULT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL DEFAULT '',
    email VARCHAR(255) DEFAULT NULL,
    wechat_openid VARCHAR(128) DEFAULT NULL,
    email_notifications_enabled TINYINT NOT NULL DEFAULT 1,
    miniapp_notifications_enabled TINYINT NOT NULL DEFAULT 1,
    notification_refresh_interval_minutes INT NOT NULL DEFAULT 60,
    last_notification_check_at DATETIME DEFAULT NULL,
    status TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_email (email),
    UNIQUE KEY uk_users_wechat_openid (wechat_openid),
    KEY idx_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SUBSCRIPTIONS_DDL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    target_type VARCHAR(32) NOT NULL DEFAULT 'department',
    target_value VARCHAR(100) NOT NULL DEFAULT '',
    status TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_subscriptions_user_target (user_id, target_type, target_value),
    KEY idx_subscriptions_target (target_type, target_value),
    KEY idx_subscriptions_status (status),
    CONSTRAINT fk_subscriptions_user_id
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

NOTIFICATION_DELIVERY_LOG_DDL = """
CREATE TABLE IF NOT EXISTS notification_delivery_log (
    id BIGINT NOT NULL AUTO_INCREMENT,
    news_id VARCHAR(64) NOT NULL,
    user_id INT NOT NULL,
    subscription_id BIGINT DEFAULT NULL,
    job_id BIGINT DEFAULT NULL,
    channel VARCHAR(32) NOT NULL DEFAULT 'email',
    recipient VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    error_msg TEXT,
    provider_message_id VARCHAR(128) DEFAULT NULL,
    sent_at DATETIME DEFAULT NULL,
    last_attempt_at DATETIME DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_delivery_news_user_channel (news_id, user_id, channel),
    KEY idx_delivery_status (status),
    KEY idx_delivery_channel (channel),
    KEY idx_delivery_job_id (job_id),
    KEY idx_delivery_user_id (user_id),
    CONSTRAINT fk_delivery_news_id
        FOREIGN KEY (news_id) REFERENCES notifications (news_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_delivery_user_id
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_delivery_subscription_id
        FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    CONSTRAINT fk_delivery_job_id
        FOREIGN KEY (job_id) REFERENCES crawl_job_log (id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def create_connection(database: str | None = config.DB_NAME) -> Connection:
    connection_args = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
        "charset": config.DB_CHARSET,
        "connect_timeout": config.DB_CONNECT_TIMEOUT,
        "autocommit": False,
    }
    if database:
        connection_args["database"] = database
    return pymysql.connect(**connection_args)


def test_connection() -> None:
    LOGGER.info(
        "Testing MySQL connection: host=%s, port=%s, database=%s, user=%s",
        config.DB_HOST,
        config.DB_PORT,
        config.DB_NAME,
        config.DB_USER,
    )
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    LOGGER.info("MySQL connection test passed")


def ensure_database_exists() -> None:
    LOGGER.info("Ensuring database exists: %s", config.DB_NAME)
    with closing(create_connection(database=None)) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                f"CHARACTER SET {config.DB_CHARSET} COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()


def initialize_schema() -> None:
    ensure_database_exists()
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(NOTIFICATIONS_DDL)
            cursor.execute(AUDIENCE_KEYWORD_RULES_DDL)
            cursor.execute(AUDIENCE_DEPARTMENT_RULES_DDL)
            try:
                cursor.execute(
                    "ALTER TABLE notifications "
                    "DROP INDEX ftx_notifications_content_text, "
                    "ADD FULLTEXT KEY ftx_notifications_content_text (content_text) WITH PARSER ngram"
                )
            except pymysql.MySQLError:
                LOGGER.warning("ngram parser unavailable, keeping default FULLTEXT parser")
            cursor.execute(ATTACHMENTS_DDL)
            cursor.execute(CRAWL_JOB_LOG_DDL)
            cursor.execute(CRAWLER_RUNTIME_CONFIG_DDL)
            cursor.execute(USERS_DDL)
            cursor.execute(SUBSCRIPTIONS_DDL)
            cursor.execute(NOTIFICATION_DELIVERY_LOG_DDL)
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_undergraduate",
                "TINYINT NOT NULL DEFAULT 0",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_undergraduate_rule_version",
                "VARCHAR(20) DEFAULT NULL",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_undergraduate_rule_detail",
                "LONGTEXT",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_graduate",
                "TINYINT NOT NULL DEFAULT 0",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_graduate_rule_version",
                "VARCHAR(20) DEFAULT NULL",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_graduate_rule_detail",
                "LONGTEXT",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_staff",
                "TINYINT NOT NULL DEFAULT 0",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_staff_rule_version",
                "VARCHAR(20) DEFAULT NULL",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "audience_staff_rule_detail",
                "LONGTEXT",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "first_seen_time",
                "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            )
            ensure_column_exists(
                cursor,
                "notifications",
                "last_seen_time",
                "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            )
            ensure_column_exists(
                cursor,
                "attachments",
                "crawl_time",
                "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            )
            drop_column_if_exists(cursor, "attachments", "download_url")
            drop_column_if_exists(cursor, "attachments", "preview_url")
            drop_column_if_exists(cursor, "attachments", "version_token")
            drop_column_if_exists(cursor, "attachments", "create_date")
            ensure_column_exists(
                cursor,
                "crawl_job_log",
                "message",
                "TEXT",
            )
            ensure_column_exists(
                cursor,
                "crawl_job_log",
                "error_message",
                "LONGTEXT",
            )
            ensure_column_exists(
                cursor,
                "users",
                "email_notifications_enabled",
                "TINYINT NOT NULL DEFAULT 1",
            )
            ensure_column_exists(
                cursor,
                "users",
                "miniapp_notifications_enabled",
                "TINYINT NOT NULL DEFAULT 1",
            )
            ensure_column_exists(
                cursor,
                "users",
                "notification_refresh_interval_minutes",
                "INT NOT NULL DEFAULT 60",
            )
            ensure_column_exists(
                cursor,
                "users",
                "last_notification_check_at",
                "DATETIME DEFAULT NULL",
            )
            drop_column_if_exists(cursor, "notifications", "audience_rule_version")
            drop_column_if_exists(cursor, "notifications", "audience_rule_detail")
            drop_column_if_exists(cursor, "subscriptions", "enable_email")
            drop_column_if_exists(cursor, "subscriptions", "enable_wechat")
            seed_default_audience_rules(cursor)
            seed_default_crawler_runtime_config(cursor)
        conn.commit()
    LOGGER.info("MySQL schema initialized")


def ensure_column_exists(cursor, table_name: str, column_name: str, definition: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (config.DB_NAME, table_name, column_name),
    )
    result = cursor.fetchone()
    exists = bool(result and result[0])
    if exists:
        return
    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
    LOGGER.info("Added missing column: %s.%s", table_name, column_name)


def drop_column_if_exists(cursor, table_name: str, column_name: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (config.DB_NAME, table_name, column_name),
    )
    result = cursor.fetchone()
    exists = bool(result and result[0])
    if not exists:
        return
    cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
    LOGGER.info("Dropped legacy column: %s.%s", table_name, column_name)


def rename_column_if_exists(
    cursor,
    table_name: str,
    old_column_name: str,
    new_column_name: str,
    definition: str,
) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (config.DB_NAME, table_name, old_column_name),
    )
    old_exists = bool(cursor.fetchone()[0])
    if not old_exists:
        return
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (config.DB_NAME, table_name, new_column_name),
    )
    new_exists = bool(cursor.fetchone()[0])
    if new_exists:
        return
    cursor.execute(
        f"ALTER TABLE {table_name} CHANGE COLUMN {old_column_name} {new_column_name} {definition}"
    )
    LOGGER.info("Renamed column: %s.%s -> %s", table_name, old_column_name, new_column_name)


def seed_default_audience_rules(cursor) -> None:
    keyword_rules = [
        ("undergraduate", "title", "本科生", 5),
        ("undergraduate", "title", "全体本科生", 6),
        ("undergraduate", "title", "本科学生", 5),
        ("undergraduate", "title", "学生", 1),
        ("undergraduate", "category", "本科", 4),
        ("undergraduate", "category", "学生", 2),
        ("undergraduate", "content_text", "本科生", 2),
        ("undergraduate", "content_text", "全体本科生", 3),
        ("undergraduate", "content_text", "本科学生", 2),
        ("undergraduate", "content_text", "学生", 1),
        ("graduate", "title", "研究生", 6),
        ("graduate", "title", "硕士生", 5),
        ("graduate", "title", "博士生", 5),
        ("graduate", "title", "研招", 4),
        ("graduate", "category", "研究生", 4),
        ("graduate", "content_text", "研究生", 3),
        ("graduate", "content_text", "硕士生", 2),
        ("graduate", "content_text", "博士生", 2),
        ("graduate", "content_text", "推免", 2),
        ("graduate", "content_text", "研招", 2),
        ("staff", "title", "教职工", 6),
        ("staff", "title", "教师", 4),
        ("staff", "title", "辅导员", 4),
        ("staff", "title", "人事", 3),
        ("staff", "category", "教师", 3),
        ("staff", "category", "教职工", 4),
        ("staff", "content_text", "教职工", 3),
        ("staff", "content_text", "教师", 2),
        ("staff", "content_text", "辅导员", 2),
        ("staff", "content_text", "专任教师", 3),
        ("staff", "content_text", "干部", 2),
    ]
    department_rules = [
        ("undergraduate", "教务处", 3),
        ("undergraduate", "学生工作部（处）", 2),
        ("undergraduate", "学生工作处", 2),
        ("undergraduate", "招生办公室", 2),
        ("undergraduate", "创新创业学院", 2),
        ("graduate", "研究生院", 4),
        ("graduate", "党委研究生工作部", 3),
        ("graduate", "学位与研究生教育发展中心", 3),
        ("graduate", "研究生工作部", 3),
        ("staff", "人力资源处", 4),
        ("staff", "党委教师工作部", 4),
        ("staff", "教师发展中心", 3),
        ("staff", "工会", 2),
        ("staff", "党委学生工作部", 1),
    ]
    cursor.executemany(
        """
        INSERT IGNORE INTO audience_keyword_rules (
            audience_type,
            rule_scope,
            keyword,
            weight,
            status,
            rule_version
        ) VALUES (%s, %s, %s, %s, 1, 'v1')
        """,
        keyword_rules,
    )
    cursor.executemany(
        """
        INSERT IGNORE INTO audience_department_rules (
            audience_type,
            department_name,
            weight,
            status,
            rule_version
        ) VALUES (%s, %s, %s, 1, 'v1')
        """,
        department_rules,
    )


def get_active_audience_keyword_rules(audience_type: str) -> list[dict]:
    sql = """
    SELECT audience_type, rule_scope, keyword, weight, rule_version
    FROM audience_keyword_rules
    WHERE audience_type = %s
      AND status = 1
    ORDER BY rule_scope ASC, weight DESC, id ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (audience_type,))
            return list(cursor.fetchall())


def get_active_audience_department_rules(audience_type: str) -> list[dict]:
    sql = """
    SELECT audience_type, department_name, weight, rule_version
    FROM audience_department_rules
    WHERE audience_type = %s
      AND status = 1
    ORDER BY weight DESC, id ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (audience_type,))
            return list(cursor.fetchall())


def evaluate_audience(notification: dict, audience_type: str) -> dict:
    text_by_scope = {
        "title": str(notification.get("title") or "").strip(),
        "category": str(notification.get("category") or "").strip(),
        "content_text": str(notification.get("content_text") or "").strip(),
    }
    department = str(notification.get("publish_department") or "").strip()
    score = 0
    matched_rules: list[dict] = []
    rule_versions: set[str] = set()

    for rule in get_active_audience_keyword_rules(audience_type):
        scope = str(rule.get("rule_scope") or "").strip()
        keyword = str(rule.get("keyword") or "").strip()
        if not scope or not keyword:
            continue
        source_text = text_by_scope.get(scope, "")
        if keyword and source_text and keyword in source_text:
            weight = int(rule.get("weight") or 0)
            score += weight
            rule_versions.add(str(rule.get("rule_version") or "v1"))
            matched_rules.append(
                {
                    "type": "keyword",
                    "scope": scope,
                    "keyword": keyword,
                    "weight": weight,
                }
            )

    for rule in get_active_audience_department_rules(audience_type):
        department_name = str(rule.get("department_name") or "").strip()
        if department and department_name and department_name in department:
            weight = int(rule.get("weight") or 0)
            score += weight
            rule_versions.add(str(rule.get("rule_version") or "v1"))
            matched_rules.append(
                {
                    "type": "department",
                    "scope": "publish_department",
                    "keyword": department_name,
                    "weight": weight,
                }
            )

    is_matched = score >= AUDIENCE_SCORE_THRESHOLD
    detail = {
        "audience": audience_type,
        "score": score,
        "matched": is_matched,
        "matched_rules": matched_rules,
    }
    field_config = AUDIENCE_FIELD_CONFIG[audience_type]
    return {
        field_config["flag"]: 1 if is_matched else 0,
        field_config["version"]: ",".join(sorted(rule_versions)) if rule_versions else "v1",
        field_config["detail"]: json.dumps(detail, ensure_ascii=False),
    }


def evaluate_undergraduate_audience(notification: dict) -> dict:
    return evaluate_audience(notification, "undergraduate")


def evaluate_all_audiences(notification: dict) -> dict:
    result: dict[str, object] = {}
    for audience_type in AUDIENCE_TYPES:
        result.update(evaluate_audience(notification, audience_type))
    return result

def normalize_datetime(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def save_notifications(notifications: list[dict]) -> tuple[int, list[dict]]:
    if not notifications:
        return 0, []

    sql = """
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
        audience_undergraduate,
        audience_undergraduate_rule_version,
        audience_undergraduate_rule_detail,
        audience_graduate,
        audience_graduate_rule_version,
        audience_graduate_rule_detail,
        audience_staff,
        audience_staff_rule_version,
        audience_staff_rule_detail,
        view_count,
        first_seen_time,
        last_seen_time,
        crawl_time
    ) VALUES (
        %(news_id)s,
        %(title)s,
        %(category)s,
        %(fragment_id)s,
        %(publish_time)s,
        %(publish_department)s,
        %(content_html)s,
        %(content_text)s,
        %(detail_url)s,
        %(audience_undergraduate)s,
        %(audience_undergraduate_rule_version)s,
        %(audience_undergraduate_rule_detail)s,
        %(audience_graduate)s,
        %(audience_graduate_rule_version)s,
        %(audience_graduate_rule_detail)s,
        %(audience_staff)s,
        %(audience_staff_rule_version)s,
        %(audience_staff_rule_detail)s,
        %(view_count)s,
        %(first_seen_time)s,
        %(last_seen_time)s,
        %(crawl_time)s
    )
    ON DUPLICATE KEY UPDATE
        title = VALUES(title),
        category = VALUES(category),
        fragment_id = VALUES(fragment_id),
        publish_time = VALUES(publish_time),
        publish_department = VALUES(publish_department),
        content_html = VALUES(content_html),
        content_text = VALUES(content_text),
        detail_url = VALUES(detail_url),
        audience_undergraduate = VALUES(audience_undergraduate),
        audience_undergraduate_rule_version = VALUES(audience_undergraduate_rule_version),
        audience_undergraduate_rule_detail = VALUES(audience_undergraduate_rule_detail),
        audience_graduate = VALUES(audience_graduate),
        audience_graduate_rule_version = VALUES(audience_graduate_rule_version),
        audience_graduate_rule_detail = VALUES(audience_graduate_rule_detail),
        audience_staff = VALUES(audience_staff),
        audience_staff_rule_version = VALUES(audience_staff_rule_version),
        audience_staff_rule_detail = VALUES(audience_staff_rule_detail),
        view_count = VALUES(view_count),
        last_seen_time = VALUES(last_seen_time),
        crawl_time = VALUES(crawl_time)
    """

    rows = []
    notification_map: dict[str, dict] = {}
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in notifications:
        news_id = str(item.get("news_id", "")).strip()
        if not news_id:
            continue
        notification_map[news_id] = item
        normalized_crawl_time = normalize_datetime(item.get("crawl_time")) or current_time
        audience_result = evaluate_all_audiences(item)
        rows.append(
            {
                "news_id": news_id,
                "title": str(item.get("title", "")).strip() or news_id,
                "category": str(item.get("category", "")).strip() or None,
                "fragment_id": str(item.get("fragment_id", "")).strip() or None,
                "publish_time": normalize_datetime(item.get("publish_time")),
                "publish_department": str(item.get("publish_department", "")).strip() or None,
                "content_html": item.get("content_html") or None,
                "content_text": item.get("content_text") or None,
                "detail_url": str(item.get("detail_url", "")).strip() or None,
                "audience_undergraduate": int(audience_result["audience_undergraduate"]),
                "audience_undergraduate_rule_version": audience_result["audience_undergraduate_rule_version"],
                "audience_undergraduate_rule_detail": audience_result["audience_undergraduate_rule_detail"],
                "audience_graduate": int(audience_result["audience_graduate"]),
                "audience_graduate_rule_version": audience_result["audience_graduate_rule_version"],
                "audience_graduate_rule_detail": audience_result["audience_graduate_rule_detail"],
                "audience_staff": int(audience_result["audience_staff"]),
                "audience_staff_rule_version": audience_result["audience_staff_rule_version"],
                "audience_staff_rule_detail": audience_result["audience_staff_rule_detail"],
                "view_count": int(item.get("read_count") or item.get("view_count") or 0),
                "first_seen_time": normalized_crawl_time,
                "last_seen_time": normalized_crawl_time,
                "crawl_time": normalized_crawl_time,
            }
        )

    if not rows:
        return 0, []

    existing_news_ids = get_existing_news_ids([row["news_id"] for row in rows])
    new_news_ids = [row["news_id"] for row in rows if row["news_id"] not in existing_news_ids]
    new_notifications = [notification_map[news_id] for news_id in new_news_ids if news_id in notification_map]

    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)
        conn.commit()
    LOGGER.info("Notifications saved: %s", len(rows))
    LOGGER.info("New notifications detected: %s", len(new_notifications))
    return len(rows), new_notifications


def save_attachments(attachments: list[dict]) -> int:
    if not attachments:
        return 0

    sql = """
    INSERT INTO attachments (
        news_id,
        file_id,
        filename,
        extension,
        size,
        crawl_time
    ) VALUES (
        %(news_id)s,
        %(file_id)s,
        %(filename)s,
        %(extension)s,
        %(size)s,
        %(crawl_time)s
    )
    ON DUPLICATE KEY UPDATE
        filename = VALUES(filename),
        extension = VALUES(extension),
        size = VALUES(size),
        crawl_time = VALUES(crawl_time)
    """

    rows = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in attachments:
        news_id = str(item.get("news_id", "")).strip()
        file_id = str(item.get("file_id", "")).strip()
        if not news_id or not file_id:
            continue
        rows.append(
            {
                "news_id": news_id,
                "file_id": file_id,
                "filename": str(item.get("filename", "")).strip() or None,
                "extension": str(item.get("extension", "")).strip() or None,
                "size": item.get("size"),
                "crawl_time": normalize_datetime(item.get("crawl_time")) or current_time,
            }
        )

    if not rows:
        return 0

    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)
        conn.commit()
    LOGGER.info("Attachments saved: %s", len(rows))
    return len(rows)


def save_crawl_result(notifications: list[dict], attachments: list[dict]) -> tuple[int, int, list[dict]]:
    saved_notifications, new_notifications = save_notifications(notifications)
    saved_attachments = save_attachments(attachments)
    return saved_notifications, saved_attachments, new_notifications


def get_existing_news_ids(news_ids: list[str]) -> set[str]:
    clean_ids = [str(news_id).strip() for news_id in news_ids if str(news_id).strip()]
    if not clean_ids:
        return set()

    placeholders = ", ".join(["%s"] * len(clean_ids))
    sql = f"SELECT news_id FROM notifications WHERE news_id IN ({placeholders})"
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, clean_ids)
            rows = cursor.fetchall()
    return {row[0] for row in rows}


def get_oldest_notifications(limit: int = 3) -> list[dict]:
    sql = """
    SELECT
        news_id,
        title,
        category,
        fragment_id,
        publish_time,
        publish_department,
        detail_url,
        content_text,
        crawl_time
    FROM notifications
    ORDER BY
        CASE WHEN publish_time IS NULL THEN 1 ELSE 0 END,
        publish_time ASC,
        id ASC
    LIMIT %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (limit,))
            return list(cursor.fetchall())


def get_latest_notifications(limit: int = 20) -> list[dict]:
    sql = """
    SELECT
        id,
        news_id,
        title,
        category,
        fragment_id,
        publish_time,
        publish_department,
        content_text,
        detail_url,
        audience_undergraduate,
        audience_undergraduate_rule_version,
        audience_graduate,
        audience_graduate_rule_version,
        audience_staff,
        audience_staff_rule_version,
        view_count,
        first_seen_time,
        last_seen_time,
        crawl_time
    FROM notifications
    ORDER BY
        CASE WHEN publish_time IS NULL THEN 1 ELSE 0 END,
        publish_time DESC,
        id DESC
    LIMIT %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (limit,))
            return list(cursor.fetchall())


def get_undergraduate_notifications(limit: int = 50) -> list[dict]:
    return get_notifications_by_audience_type("undergraduate", limit=limit)


def get_notifications_by_audience_type(audience_type: str, limit: int = 50) -> list[dict]:
    field_config = AUDIENCE_FIELD_CONFIG.get(audience_type)
    if not field_config:
        raise ValueError(f"Unsupported audience_type: {audience_type}")
    sql = """
    SELECT
        id,
        news_id,
        title,
        category,
        fragment_id,
        publish_time,
        publish_department,
        content_text,
        detail_url,
        {flag_column} AS audience_flag,
        {version_column} AS audience_rule_version,
        {detail_column} AS audience_rule_detail,
        view_count,
        first_seen_time,
        last_seen_time,
        crawl_time
    FROM notifications
    WHERE {flag_column} = 1
    ORDER BY
        CASE WHEN publish_time IS NULL THEN 1 ELSE 0 END,
        publish_time DESC,
        id DESC
    LIMIT %s
    """.format(
        flag_column=field_config["flag"],
        version_column=field_config["version"],
        detail_column=field_config["detail"],
    )
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (limit,))
            return list(cursor.fetchall())


def recompute_notification_audiences(news_ids: list[str] | None = None) -> int:
    select_sql = """
    SELECT
        news_id,
        title,
        category,
        publish_department,
        content_text
    FROM notifications
    """
    params: list[object] = []
    if news_ids:
        placeholders = ", ".join(["%s"] * len(news_ids))
        select_sql += f" WHERE news_id IN ({placeholders})"
        params.extend(news_ids)

    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(select_sql, params)
            rows = list(cursor.fetchall())
            if not rows:
                return 0
            update_sql = """
            UPDATE notifications
            SET audience_undergraduate = %(audience_undergraduate)s,
                audience_undergraduate_rule_version = %(audience_undergraduate_rule_version)s,
                audience_undergraduate_rule_detail = %(audience_undergraduate_rule_detail)s,
                audience_graduate = %(audience_graduate)s,
                audience_graduate_rule_version = %(audience_graduate_rule_version)s,
                audience_graduate_rule_detail = %(audience_graduate_rule_detail)s,
                audience_staff = %(audience_staff)s,
                audience_staff_rule_version = %(audience_staff_rule_version)s,
                audience_staff_rule_detail = %(audience_staff_rule_detail)s
            WHERE news_id = %(news_id)s
            """
            payload = []
            for row in rows:
                audience_result = evaluate_all_audiences(row)
                audience_result["news_id"] = row["news_id"]
                payload.append(audience_result)
            cursor.executemany(update_sql, payload)
        conn.commit()
    LOGGER.info("Recomputed notification audiences: %s", len(rows))
    return len(rows)


def get_notifications_total_count() -> int:
    sql = "SELECT COUNT(*) FROM notifications"
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
    return int(row[0]) if row else 0


def get_notification_by_news_id(news_id: str) -> dict | None:
    sql = """
    SELECT
        id,
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
    FROM notifications
    WHERE news_id = %s
    LIMIT 1
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (news_id,))
            row = cursor.fetchone()
    return dict(row) if row else None


def get_attachments_by_news_id(news_id: str) -> list[dict]:
    sql = """
    SELECT
        file_id,
        filename,
        extension,
        size,
        crawl_time
    FROM attachments
    WHERE news_id = %s
    ORDER BY id ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (news_id,))
            return list(cursor.fetchall())


def get_user_by_email(email: str) -> dict | None:
    sql = """
    SELECT
        id,
        username,
        email,
        wechat_openid,
        email_notifications_enabled,
        miniapp_notifications_enabled,
        notification_refresh_interval_minutes,
        last_notification_check_at,
        status,
        created_at,
        updated_at
    FROM users
    WHERE email = %s
    LIMIT 1
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (email,))
            row = cursor.fetchone()
    return dict(row) if row else None


def update_user_wechat_openid(email: str, openid: str) -> bool:
    clean_email = str(email or "").strip()
    clean_openid = str(openid or "").strip()
    if not clean_email or not clean_openid:
        return False
    sql = """
    UPDATE users
    SET wechat_openid = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE email = %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, (clean_openid, clean_email))
        conn.commit()
    LOGGER.info("Updated user wechat_openid: email=%s, affected=%s", clean_email, affected)
    return bool(affected)


def ensure_demo_miniapp_user(email: str, username: str = "小程序测试用户") -> int:
    email = str(email or "").strip()
    if not email:
        return 0
    existing = get_user_by_email(email)
    if existing:
        return int(existing["id"])

    sql = """
    INSERT INTO users (
        username,
        email,
        wechat_openid,
        email_notifications_enabled,
        miniapp_notifications_enabled,
        notification_refresh_interval_minutes,
        last_notification_check_at,
        status
    )
    VALUES (%s, %s, NULL, 1, 1, 60, CURRENT_TIMESTAMP, 1)
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (username, email))
            user_id = int(cursor.lastrowid)
        conn.commit()
    LOGGER.info("Demo miniapp user ensured: email=%s, user_id=%s", email, user_id)
    return user_id


def ensure_department_subscriptions_for_user(
    user_id: int,
) -> int:
    LOGGER.info(
        "Department subscription auto-init skipped: user_id=%s",
        user_id,
    )
    return 0


def get_user_department_subscriptions(email: str) -> list[dict]:
    clean_email = str(email or "").strip()
    if not clean_email:
        return []
    sql = """
    SELECT
        s.id,
        s.target_value,
        s.status
    FROM subscriptions s
    INNER JOIN users u
        ON u.id = s.user_id
    WHERE u.email = %s
      AND s.target_type = 'department'
      AND s.status = 1
    ORDER BY s.target_value ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (clean_email,))
            return list(cursor.fetchall())


def get_department_subscription_status(email: str, department: str) -> dict | None:
    clean_email = str(email or "").strip()
    clean_department = str(department or "").strip()
    if not clean_email or not clean_department:
        return None
    sql = """
    SELECT
        s.id,
        s.target_value,
        s.status
    FROM subscriptions s
    INNER JOIN users u
        ON u.id = s.user_id
    WHERE u.email = %s
      AND s.target_type = 'department'
      AND s.target_value = %s
    LIMIT 1
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (clean_email, clean_department))
            row = cursor.fetchone()
    return dict(row) if row else None


def upsert_department_subscription(email: str, department: str) -> dict:
    clean_email = str(email or "").strip()
    clean_department = str(department or "").strip()
    if not clean_email or not clean_department:
        raise ValueError("email and department are required")

    user_id = ensure_demo_miniapp_user(clean_email, username=clean_email.split("@")[0] or "miniapp_user")
    existing = get_department_subscription_status(clean_email, clean_department)
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            if existing:
                cursor.execute(
                    """
                    UPDATE subscriptions
                    SET status = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (int(existing["id"]),),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (
                        user_id,
                        target_type,
                        target_value,
                        status
                    ) VALUES (
                        %s,
                        'department',
                        %s,
                        1
                    )
                    """,
                    (user_id, clean_department),
                )
        conn.commit()
    result = get_department_subscription_status(clean_email, clean_department)
    return result or {
        "target_value": clean_department,
        "status": 1,
    }


def save_department_subscription_settings(
    email: str,
    department: str,
    *,
    subscribed: bool,
) -> dict | None:
    clean_email = str(email or "").strip()
    clean_department = str(department or "").strip()
    if not clean_email or not clean_department:
        raise ValueError("email and department are required")

    user_id = ensure_demo_miniapp_user(clean_email, username=clean_email.split("@")[0] or "miniapp_user")
    existing = get_department_subscription_status(clean_email, clean_department)
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            if existing:
                cursor.execute(
                    """
                    UPDATE subscriptions
                    SET status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (1 if subscribed else 0, int(existing["id"])),
                )
            elif subscribed:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (
                        user_id,
                        target_type,
                        target_value,
                        status
                    ) VALUES (
                        %s,
                        'department',
                        %s,
                        1
                    )
                    """,
                    (user_id, clean_department),
                )
        conn.commit()

    if not subscribed:
        return None
    return get_department_subscription_status(clean_email, clean_department)


def save_user_department_subscriptions(email: str, subscriptions: list[dict]) -> list[dict]:
    clean_email = str(email or "").strip()
    if not clean_email:
        raise ValueError("email is required")

    results: list[dict] = []
    for item in subscriptions:
        department = str((item or {}).get("department") or "").strip()
        if not department:
            continue
        subscribed = bool((item or {}).get("subscribed"))
        result = save_department_subscription_settings(
            clean_email,
            department,
            subscribed=subscribed,
        )
        if result:
            results.append(result)
    return get_user_department_subscriptions(clean_email)


def get_user_notification_settings(email: str) -> dict | None:
    clean_email = str(email or "").strip()
    if not clean_email:
        return None
    sql = """
    SELECT
        id,
        username,
        email,
        email_notifications_enabled,
        miniapp_notifications_enabled,
        notification_refresh_interval_minutes,
        last_notification_check_at,
        status,
        created_at,
        updated_at
    FROM users
    WHERE email = %s
    LIMIT 1
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (clean_email,))
            row = cursor.fetchone()
    return dict(row) if row else None


def upsert_user_notification_settings(
    email: str,
    *,
    refresh_interval_minutes: int | None = None,
    email_enabled: bool | None = None,
    miniapp_enabled: bool | None = None,
) -> dict:
    clean_email = str(email or "").strip()
    if not clean_email:
        raise ValueError("email is required")
    if refresh_interval_minutes is None and email_enabled is None and miniapp_enabled is None:
        raise ValueError("at least one setting is required")

    interval: int | None = None
    if refresh_interval_minutes is not None:
        interval = int(refresh_interval_minutes or 0)
        if interval not in (1, 5, 30, 60):
            raise ValueError("refresh_interval_minutes must be one of 1, 5, 30, 60")

    ensure_demo_miniapp_user(clean_email, username=clean_email.split("@")[0] or "miniapp_user")
    current = get_user_notification_settings(clean_email) or {}
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_interval = interval if interval is not None else int(current.get("notification_refresh_interval_minutes") or 60)
    next_email_enabled = int(email_enabled) if email_enabled is not None else int(current.get("email_notifications_enabled") or 0)
    next_miniapp_enabled = int(miniapp_enabled) if miniapp_enabled is not None else int(current.get("miniapp_notifications_enabled") or 0)
    next_last_check_at = now_text if interval is not None else current.get("last_notification_check_at") or now_text

    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET email_notifications_enabled = %s,
                    miniapp_notifications_enabled = %s,
                    notification_refresh_interval_minutes = %s,
                    last_notification_check_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE email = %s
                """,
                (
                    next_email_enabled,
                    next_miniapp_enabled,
                    next_interval,
                    next_last_check_at,
                    clean_email,
                ),
            )
        conn.commit()

    result = get_user_notification_settings(clean_email)
    if not result:
        raise RuntimeError("failed to load saved notification settings")
    return result


def ensure_demo_miniapp_user_and_subscriptions(email: str, username: str = "小程序测试用户") -> int:
    user_id = ensure_demo_miniapp_user(email, username=username)
    if not user_id:
        return 0
    return user_id


def get_due_users_for_notification_check() -> list[dict]:
    sql = """
    SELECT
        u.id,
        u.username,
        u.email,
        u.wechat_openid,
        u.email_notifications_enabled,
        u.miniapp_notifications_enabled,
        u.notification_refresh_interval_minutes,
        u.last_notification_check_at,
        u.created_at
    FROM users u
    WHERE u.status = 1
      AND (
          u.email_notifications_enabled = 1
          OR u.miniapp_notifications_enabled = 1
      )
      AND EXISTS (
          SELECT 1
          FROM subscriptions s
          WHERE s.user_id = u.id
            AND s.status = 1
      )
      AND (
          u.last_notification_check_at IS NULL
          OR TIMESTAMPDIFF(
              MINUTE,
              u.last_notification_check_at,
              CURRENT_TIMESTAMP
          ) >= u.notification_refresh_interval_minutes
      )
    ORDER BY u.id ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            return list(cursor.fetchall())


def count_user_new_notifications_since(user_id: int, since_time) -> int:
    sql = """
    SELECT COUNT(DISTINCT n.news_id)
    FROM notifications n
    INNER JOIN users u
        ON u.id = %s
       AND u.status = 1
    INNER JOIN subscriptions s
        ON s.user_id = u.id
       AND s.target_type = 'department'
       AND s.target_value = n.publish_department
       AND s.status = 1
    WHERE COALESCE(n.first_seen_time, n.crawl_time, n.publish_time) > %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (user_id, since_time))
            row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def create_due_delivery_records_for_user(
    user_id: int,
    since_time,
    *,
    job_id: int | None = None,
) -> dict:
    email_sql = """
    INSERT IGNORE INTO notification_delivery_log (
        news_id,
        user_id,
        subscription_id,
        job_id,
        channel,
        recipient,
        status
    )
    SELECT
        n.news_id,
        u.id,
        s.id,
        %s,
        'email',
        u.email,
        'pending'
    FROM users u
    INNER JOIN subscriptions s
        ON s.user_id = u.id
       AND s.target_type = 'department'
       AND s.status = 1
       AND u.email_notifications_enabled = 1
    INNER JOIN notifications n
        ON n.publish_department = s.target_value
    WHERE u.id = %s
      AND u.status = 1
      AND u.email IS NOT NULL
      AND u.email <> ''
      AND COALESCE(n.first_seen_time, n.crawl_time, n.publish_time) > %s
    """
    miniapp_sql = """
    INSERT IGNORE INTO notification_delivery_log (
        news_id,
        user_id,
        subscription_id,
        job_id,
        channel,
        recipient,
        status
    )
    SELECT
        n.news_id,
        u.id,
        s.id,
        %s,
        'miniapp',
        COALESCE(NULLIF(u.email, ''), u.username, CAST(u.id AS CHAR)),
        'pending'
    FROM users u
    INNER JOIN subscriptions s
        ON s.user_id = u.id
       AND s.target_type = 'department'
       AND s.status = 1
       AND u.miniapp_notifications_enabled = 1
    INNER JOIN notifications n
        ON n.publish_department = s.target_value
    WHERE u.id = %s
      AND u.status = 1
      AND COALESCE(n.first_seen_time, n.crawl_time, n.publish_time) > %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            email_created = cursor.execute(email_sql, (job_id, user_id, since_time))
            miniapp_created = cursor.execute(miniapp_sql, (job_id, user_id, since_time))
        conn.commit()
    return {
        "email_created": int(email_created or 0),
        "miniapp_created": int(miniapp_created or 0),
    }


def update_user_last_notification_check_at(user_id: int, checked_at: str | None = None) -> int:
    checked_time = checked_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
    UPDATE users
    SET last_notification_check_at = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, (checked_time, user_id))
        conn.commit()
    return int(affected or 0)


def create_miniapp_delivery_records(
    notifications: list[dict],
    *,
    job_id: int | None = None,
) -> int:
    if not notifications:
        return 0

    news_ids = [str(item.get("news_id", "")).strip() for item in notifications if str(item.get("news_id", "")).strip()]
    if not news_ids:
        return 0

    placeholders = ", ".join(["%s"] * len(news_ids))
    sql = f"""
    SELECT
        n.news_id,
        u.id AS user_id,
        u.username,
        u.email,
        s.id AS subscription_id
    FROM notifications n
    INNER JOIN subscriptions s
        ON s.target_type = 'department'
       AND s.target_value = n.publish_department
       AND s.status = 1
    INNER JOIN users u
        ON u.id = s.user_id
       AND u.status = 1
       AND u.miniapp_notifications_enabled = 1
    WHERE n.news_id IN ({placeholders})
    """
    insert_sql = """
    INSERT IGNORE INTO notification_delivery_log (
        news_id,
        user_id,
        subscription_id,
        job_id,
        channel,
        recipient,
        status
    ) VALUES (
        %(news_id)s,
        %(user_id)s,
        %(subscription_id)s,
        %(job_id)s,
        'miniapp',
        %(recipient)s,
        'pending'
    )
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, news_ids)
            matched_rows = list(cursor.fetchall())
            if not matched_rows:
                return 0
            params = [
                {
                    "news_id": row["news_id"],
                    "user_id": row["user_id"],
                    "subscription_id": row["subscription_id"],
                    "job_id": job_id,
                    "recipient": row["email"] or row["username"] or str(row["user_id"]),
                }
                for row in matched_rows
            ]
            inserted = cursor.executemany(insert_sql, params)
        conn.commit()
    LOGGER.info("Miniapp delivery records created: %s", inserted)
    return inserted


def ensure_miniapp_delivery_records_for_user(email: str, *, limit: int = 20) -> int:
    email = str(email or "").strip()
    if not email:
        return 0
    user_id = ensure_demo_miniapp_user(email, username=email.split("@")[0] or "miniapp_user")
    if not user_id:
        return 0
    notifications = get_latest_notifications(limit=limit)
    normalized = [{"news_id": item["news_id"]} for item in notifications if item.get("news_id")]
    return create_miniapp_delivery_records(normalized)


def get_miniapp_delivery_rows(email: str, *, limit: int = 20) -> list[dict]:
    email = str(email or "").strip()
    if not email:
        return []
    sql = """
    SELECT
        d.id AS delivery_id,
        d.news_id,
        d.status,
        d.created_at,
        d.updated_at,
        n.title,
        n.publish_department,
        n.publish_time,
        n.detail_url,
        n.content_text
    FROM notification_delivery_log d
    INNER JOIN users u
        ON u.id = d.user_id
    INNER JOIN notifications n
        ON n.news_id = d.news_id
    WHERE d.channel = 'miniapp'
      AND u.email = %s
    ORDER BY
        CASE WHEN n.publish_time IS NULL THEN 1 ELSE 0 END,
        n.publish_time DESC,
        d.id DESC
    LIMIT %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (email, limit))
            return list(cursor.fetchall())


def get_miniapp_delivery_ids_by_user_and_news(email: str, news_id: str) -> list[int]:
    clean_email = str(email or "").strip()
    clean_news_id = str(news_id or "").strip()
    if not clean_email or not clean_news_id:
        return []
    sql = """
    SELECT d.id
    FROM notification_delivery_log d
    INNER JOIN users u
        ON u.id = d.user_id
    WHERE d.channel = 'miniapp'
      AND u.email = %s
      AND d.news_id = %s
    ORDER BY d.id ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (clean_email, clean_news_id))
            rows = cursor.fetchall()
    return [int(row[0]) for row in rows]


def mark_miniapp_deliveries_read(email: str, delivery_ids: list[int]) -> int:
    email = str(email or "").strip()
    clean_ids = [int(item) for item in delivery_ids if item]
    if not email or not clean_ids:
        return 0
    placeholders = ", ".join(["%s"] * len(clean_ids))
    sql = f"""
    UPDATE notification_delivery_log d
    INNER JOIN users u
        ON u.id = d.user_id
    SET d.status = 'read',
        d.last_attempt_at = CURRENT_TIMESTAMP,
        d.updated_at = CURRENT_TIMESTAMP
    WHERE d.channel = 'miniapp'
      AND u.email = %s
      AND d.id IN ({placeholders})
    """
    params: list[object] = [email]
    params.extend(clean_ids)
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, params)
        conn.commit()
    LOGGER.info("Miniapp deliveries marked read: email=%s, count=%s", email, affected)
    return int(affected or 0)


def create_email_delivery_records(
    notifications: list[dict],
    *,
    job_id: int | None = None,
) -> int:
    if not notifications:
        return 0

    news_ids = [str(item.get("news_id", "")).strip() for item in notifications if str(item.get("news_id", "")).strip()]
    if not news_ids:
        return 0

    placeholders = ", ".join(["%s"] * len(news_ids))
    sql = f"""
    SELECT
        n.news_id,
        n.title,
        n.publish_department,
        n.publish_time,
        n.detail_url,
        u.id AS user_id,
        u.username,
        u.email,
        s.id AS subscription_id
    FROM notifications n
    INNER JOIN subscriptions s
        ON s.target_type = 'department'
       AND s.target_value = n.publish_department
       AND s.status = 1
    INNER JOIN users u
        ON u.id = s.user_id
       AND u.status = 1
       AND u.email_notifications_enabled = 1
       AND u.email IS NOT NULL
       AND u.email <> ''
    WHERE n.news_id IN ({placeholders})
    """
    insert_sql = """
    INSERT IGNORE INTO notification_delivery_log (
        news_id,
        user_id,
        subscription_id,
        job_id,
        channel,
        recipient,
        status
    ) VALUES (
        %(news_id)s,
        %(user_id)s,
        %(subscription_id)s,
        %(job_id)s,
        'email',
        %(recipient)s,
        'pending'
    )
    """

    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, news_ids)
            matched_rows = list(cursor.fetchall())
            if not matched_rows:
                return 0
            params = [
                {
                    "news_id": row["news_id"],
                    "user_id": row["user_id"],
                    "subscription_id": row["subscription_id"],
                    "job_id": job_id,
                    "recipient": row["email"],
                }
                for row in matched_rows
            ]
            inserted = cursor.executemany(insert_sql, params)
        conn.commit()
    LOGGER.info("Email delivery records created: %s", inserted)
    return inserted


def get_pending_email_deliveries(*, job_id: int | None = None) -> list[dict]:
    sql = """
    SELECT
        d.id AS delivery_id,
        d.news_id,
        d.user_id,
        d.subscription_id,
        d.job_id,
        d.recipient,
        d.status,
        u.username,
        n.title,
        n.category,
        n.fragment_id,
        n.publish_time,
        n.publish_department,
        n.detail_url,
        n.content_text
    FROM notification_delivery_log d
    INNER JOIN users u
        ON u.id = d.user_id
       AND u.email_notifications_enabled = 1
    INNER JOIN notifications n
        ON n.news_id = d.news_id
    LEFT JOIN subscriptions s
        ON s.id = d.subscription_id
    WHERE d.channel = 'email'
      AND d.status = 'pending'
      AND (s.id IS NULL OR s.status = 1)
    """
    params: list[object] = []
    if job_id is not None:
        sql += " AND d.job_id = %s"
        params.append(job_id)
    sql += " ORDER BY d.user_id ASC, n.publish_time ASC, d.id ASC"

    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())


def get_pending_miniapp_deliveries(*, job_id: int | None = None) -> list[dict]:
    sql = """
    SELECT
        d.id AS delivery_id,
        d.news_id,
        d.user_id,
        d.subscription_id,
        d.job_id,
        d.recipient,
        d.status,
        u.username,
        u.email,
        u.wechat_openid,
        n.title,
        n.category,
        n.fragment_id,
        n.publish_time,
        n.publish_department,
        n.detail_url,
        n.content_text
    FROM notification_delivery_log d
    INNER JOIN users u
        ON u.id = d.user_id
       AND u.miniapp_notifications_enabled = 1
    INNER JOIN notifications n
        ON n.news_id = d.news_id
    LEFT JOIN subscriptions s
        ON s.id = d.subscription_id
    WHERE d.channel = 'miniapp'
      AND d.status = 'pending'
      AND (s.id IS NULL OR s.status = 1)
    """
    params: list[object] = []
    if job_id is not None:
        sql += " AND d.job_id = %s"
        params.append(job_id)
    sql += " ORDER BY d.user_id ASC, n.publish_time ASC, d.id ASC"

    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())


def mark_delivery_success(delivery_ids: list[int], provider_message_id: str | None = None) -> None:
    clean_ids = [int(item) for item in delivery_ids if item]
    if not clean_ids:
        return
    placeholders = ", ".join(["%s"] * len(clean_ids))
    sql = f"""
    UPDATE notification_delivery_log
    SET status = 'success',
        sent_at = CURRENT_TIMESTAMP,
        last_attempt_at = CURRENT_TIMESTAMP,
        provider_message_id = %s,
        error_msg = NULL
    WHERE id IN ({placeholders})
    """
    params: list[object] = [provider_message_id]
    params.extend(clean_ids)
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()


def mark_delivery_failed(delivery_ids: list[int], error_message: str) -> None:
    clean_ids = [int(item) for item in delivery_ids if item]
    if not clean_ids:
        return
    placeholders = ", ".join(["%s"] * len(clean_ids))
    sql = f"""
    UPDATE notification_delivery_log
    SET status = 'failed',
        retry_count = retry_count + 1,
        last_attempt_at = CURRENT_TIMESTAMP,
        error_msg = %s
    WHERE id IN ({placeholders})
    """
    params: list[object] = [error_message[:1000]]
    params.extend(clean_ids)
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()


def create_crawl_job_log(
    *,
    job_type: str,
    trigger_mode: str,
    status: str,
    incremental_mode: int,
    scheduler_enabled: bool,
    interval_hours: int | None,
    message: str | None = None,
) -> int:
    sql = """
    INSERT INTO crawl_job_log (
        job_type,
        trigger_mode,
        status,
        incremental_mode,
        scheduler_enabled,
        interval_hours,
        started_at,
        message
    ) VALUES (
        %(job_type)s,
        %(trigger_mode)s,
        %(status)s,
        %(incremental_mode)s,
        %(scheduler_enabled)s,
        %(interval_hours)s,
        %(started_at)s,
        %(message)s
    )
    """
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "job_type": job_type,
                    "trigger_mode": trigger_mode,
                    "status": status,
                    "incremental_mode": incremental_mode,
                    "scheduler_enabled": int(scheduler_enabled),
                    "interval_hours": interval_hours,
                    "started_at": started_at,
                    "message": message,
                },
            )
            job_id = int(cursor.lastrowid)
        conn.commit()
    LOGGER.info("Crawl job log created: id=%s", job_id)
    return job_id


def update_crawl_job_log(
    job_id: int,
    *,
    status: str,
    notifications_count: int = 0,
    attachments_count: int = 0,
    db_notifications_count: int = 0,
    db_attachments_count: int = 0,
    message: str | None = None,
    error_message: str | None = None,
) -> None:
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
    UPDATE crawl_job_log
    SET status = %(status)s,
        finished_at = %(finished_at)s,
        duration_seconds = TIMESTAMPDIFF(SECOND, started_at, %(finished_at)s),
        notifications_count = %(notifications_count)s,
        attachments_count = %(attachments_count)s,
        db_notifications_count = %(db_notifications_count)s,
        db_attachments_count = %(db_attachments_count)s,
        message = %(message)s,
        error_message = %(error_message)s
    WHERE id = %(job_id)s
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "job_id": job_id,
                    "status": status,
                    "finished_at": finished_at,
                    "notifications_count": notifications_count,
                    "attachments_count": attachments_count,
                    "db_notifications_count": db_notifications_count,
                    "db_attachments_count": db_attachments_count,
                    "message": message,
                    "error_message": error_message,
                },
            )
        conn.commit()
    LOGGER.info("Crawl job log updated: id=%s, status=%s", job_id, status)


def seed_default_crawler_runtime_config(cursor) -> None:
    defaults = [
        ("SCHEDULER_ENABLED", "1" if config.SCHEDULER_ENABLED else "0", "bool", "Whether the global crawler scheduler is enabled"),
        ("SCHEDULER_INTERVAL_MINUTES", str(config.SCHEDULER_INTERVAL_MINUTES), "float", "Global crawler scheduler interval in minutes"),
        ("SCHEDULER_MAX_RUNS", str(config.SCHEDULER_MAX_RUNS), "int", "Maximum scheduler runs, 0 or less means unlimited"),
        ("MAX_RECORDS", str(config.MAX_RECORDS), "int", "Maximum records fetched in one crawl run"),
        ("REQUEST_DELAY_MIN", str(config.REQUEST_DELAY_MIN), "float", "Minimum delay between crawler requests in seconds"),
        ("REQUEST_DELAY_MAX", str(config.REQUEST_DELAY_MAX), "float", "Maximum delay between crawler requests in seconds"),
    ]
    sql = """
    INSERT INTO crawler_runtime_config (config_key, config_value, config_type, description)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        config_type = VALUES(config_type),
        description = VALUES(description)
    """
    cursor.executemany(sql, defaults)


def _parse_runtime_config_value(config_key: str, config_value: str, config_type: str):
    if config_type == "bool":
        return str(config_value).strip() in ("1", "true", "True")
    if config_type == "int":
        return int(float(config_value))
    if config_type == "float":
        return float(config_value)
    return config_value


def get_crawler_runtime_config() -> dict:
    sql = """
    SELECT config_key, config_value, config_type, description, updated_at
    FROM crawler_runtime_config
    ORDER BY config_key ASC
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            rows = list(cursor.fetchall())

    config_map = {}
    for row in rows:
        key = row["config_key"]
        config_map[key] = {
            "key": key,
            "value": _parse_runtime_config_value(
                key,
                row.get("config_value", ""),
                row.get("config_type", "string"),
            ),
            "type": row.get("config_type") or "string",
            "description": row.get("description") or "",
            "updatedAt": row.get("updated_at"),
        }
    return config_map


def update_crawler_runtime_config(
    *,
    scheduler_enabled: bool | None = None,
    scheduler_interval_minutes: float | None = None,
    scheduler_max_runs: int | None = None,
    max_records: int | None = None,
    request_delay_min: float | None = None,
    request_delay_max: float | None = None,
) -> dict:
    updates: list[tuple[str, str]] = []
    if scheduler_enabled is not None:
        updates.append(("SCHEDULER_ENABLED", "1" if scheduler_enabled else "0"))
    if scheduler_interval_minutes is not None:
        if scheduler_interval_minutes <= 0:
            raise ValueError("schedulerIntervalMinutes must be greater than 0")
        updates.append(("SCHEDULER_INTERVAL_MINUTES", str(scheduler_interval_minutes)))
    if scheduler_max_runs is not None:
        updates.append(("SCHEDULER_MAX_RUNS", str(int(scheduler_max_runs))))
    if max_records is not None:
        if max_records <= 0:
            raise ValueError("maxRecords must be greater than 0")
        updates.append(("MAX_RECORDS", str(int(max_records))))
    if request_delay_min is not None:
        if request_delay_min < 0:
            raise ValueError("requestDelayMin must be greater than or equal to 0")
        updates.append(("REQUEST_DELAY_MIN", str(request_delay_min)))
    if request_delay_max is not None:
        if request_delay_max < 0:
            raise ValueError("requestDelayMax must be greater than or equal to 0")
        updates.append(("REQUEST_DELAY_MAX", str(request_delay_max)))
    if request_delay_min is not None and request_delay_max is not None and request_delay_min > request_delay_max:
        raise ValueError("requestDelayMin cannot be greater than requestDelayMax")

    if not updates:
        return get_crawler_runtime_config()

    sql = """
    INSERT INTO crawler_runtime_config (config_key, config_value, config_type, description)
    VALUES (%s, %s, 'string', '')
    ON DUPLICATE KEY UPDATE
        config_value = VALUES(config_value)
    """
    with closing(create_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, updates)
        conn.commit()
    return get_crawler_runtime_config()


def apply_crawler_runtime_config() -> dict:
    runtime_config = get_crawler_runtime_config()
    if not runtime_config:
        return {}
    config.SCHEDULER_ENABLED = bool(runtime_config["SCHEDULER_ENABLED"]["value"])
    config.SCHEDULER_INTERVAL_MINUTES = float(runtime_config["SCHEDULER_INTERVAL_MINUTES"]["value"])
    config.SCHEDULER_MAX_RUNS = int(runtime_config["SCHEDULER_MAX_RUNS"]["value"])
    config.MAX_RECORDS = int(runtime_config["MAX_RECORDS"]["value"])
    config.REQUEST_DELAY_MIN = float(runtime_config["REQUEST_DELAY_MIN"]["value"])
    config.REQUEST_DELAY_MAX = float(runtime_config["REQUEST_DELAY_MAX"]["value"])
    return runtime_config


def get_crawl_job_logs(limit: int = 20, offset: int = 0) -> list[dict]:
    sql = """
    SELECT
        id,
        job_type,
        trigger_mode,
        status,
        incremental_mode,
        scheduler_enabled,
        interval_hours,
        started_at,
        finished_at,
        duration_seconds,
        notifications_count,
        attachments_count,
        db_notifications_count,
        db_attachments_count,
        message,
        error_message,
        created_at,
        updated_at
    FROM crawl_job_log
    ORDER BY started_at DESC, id DESC
    LIMIT %s OFFSET %s
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (limit, offset))
            return list(cursor.fetchall())


def get_crawl_job_logs_total_count() -> int:
    sql = "SELECT COUNT(*) AS total_count FROM crawl_job_log"
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
    return int((row or {}).get("total_count") or 0)


def get_crawl_job_log_by_id(job_id: int) -> dict | None:
    sql = """
    SELECT
        id,
        job_type,
        trigger_mode,
        status,
        incremental_mode,
        scheduler_enabled,
        interval_hours,
        started_at,
        finished_at,
        duration_seconds,
        notifications_count,
        attachments_count,
        db_notifications_count,
        db_attachments_count,
        message,
        error_message,
        created_at,
        updated_at
    FROM crawl_job_log
    WHERE id = %s
    LIMIT 1
    """
    with closing(create_connection()) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (job_id,))
            return cursor.fetchone()
