import json
import logging
import re
import sys
import threading
from datetime import datetime
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from oa_crawler import config
from oa_crawler.db import (
    apply_crawler_runtime_config,
    ensure_demo_miniapp_user,
    ensure_miniapp_delivery_records_for_user,
    get_crawl_job_log_by_id,
    get_crawl_job_logs,
    get_crawl_job_logs_total_count,
    get_crawler_runtime_config,
    get_attachments_by_news_id,
    get_department_subscription_status,
    get_latest_notifications,
    get_notifications_by_audience_type,
    get_undergraduate_notifications,
    get_miniapp_delivery_ids_by_user_and_news,
    get_miniapp_delivery_rows,
    get_notification_by_news_id,
    get_notifications_total_count,
    get_user_notification_settings,
    get_user_by_email,
    get_user_department_subscriptions,
    initialize_schema,
    save_user_department_subscriptions,
    mark_delivery_failed,
    mark_delivery_success,
    mark_miniapp_deliveries_read,
    test_connection,
    upsert_department_subscription,
    update_crawler_runtime_config,
    upsert_user_notification_settings,
    update_user_wechat_openid,
)
from oa_crawler.miniapp_notifier import (
    MiniappNotifierError,
    exchange_code_for_openid,
    miniapp_is_configured,
    send_subscribe_message,
)
from oa_crawler_main import run_once as run_crawler_once


HOST = "0.0.0.0"
PORT = 8000
ADMIN_CRAWLER_RUN_STATE = {
    "running": False,
    "lastStartedAt": "",
    "lastFinishedAt": "",
    "lastStatus": "",
    "lastMessage": "",
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


LOGGER = logging.getLogger("oa_api")


def format_datetime(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def build_summary(content_text: str | None, limit: int = 56) -> str:
    if not content_text:
        return ""
    text = " ".join(str(content_text).split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def make_absolute_url(path: str | None) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{config.BASE_URL}{path}"


def extract_image_urls(content_html: str | None) -> list[str]:
    if not content_html:
        return []
    urls: list[str] = []
    for match in re.finditer(r'<img[^>]+src=["\'](?P<src>[^"\']+)["\']', content_html, re.S | re.I):
        image_url = make_absolute_url(unescape(match.group("src")).strip())
        if image_url and image_url not in urls:
            urls.append(image_url)
    return urls


def build_miniapp_content_html(content_html: str | None) -> str:
    if not content_html:
        return ""

    html = str(content_html)
    content_match = re.search(
        r'<div[^>]+id=["\']content["\'][^>]*>(?P<body>.*?)</div>',
        html,
        flags=re.S | re.I,
    )
    if content_match:
        html = content_match.group("body")

    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"</?(table|tbody|tr|td|colgroup)\b[^>]*>", "", html, flags=re.S | re.I)
    html = re.sub(r"<col\b[^>]*>", "", html, flags=re.S | re.I)
    html = re.sub(r"</?(span|font|o:p)\b[^>]*>", "", html, flags=re.S | re.I)
    html = html.replace("&nbsp;", " ")

    def replace_src(match: re.Match) -> str:
        quote = match.group("quote")
        src = make_absolute_url(unescape(match.group("src")).strip())
        return f'src={quote}{src}{quote}'

    def replace_href(match: re.Match) -> str:
        quote = match.group("quote")
        href = make_absolute_url(unescape(match.group("href")).strip())
        return f'href={quote}{href}{quote}'

    def normalize_img(match: re.Match) -> str:
        attrs = match.group("attrs") or ""
        src_match = re.search(r'src=(["\'])(?P<src>.*?)\1', attrs, re.S | re.I)
        if not src_match:
            return ""
        src = make_absolute_url(unescape(src_match.group("src")).strip())
        return (
            '<img '
            f'src="{src}" '
            'mode="widthFix" '
            'style="display:block;max-width:88%;height:auto;margin:20px auto;border-radius:10px;"'
            ">"
        )

    html = re.sub(
        r'src=(?P<quote>[\'"])(?P<src>.*?)(?P=quote)',
        replace_src,
        html,
        flags=re.S | re.I,
    )
    html = re.sub(
        r'href=(?P<quote>[\'"])(?P<href>.*?)(?P=quote)',
        replace_href,
        html,
        flags=re.S | re.I,
    )
    html = re.sub(r"<img(?P<attrs>[^>]*)>", normalize_img, html, flags=re.S | re.I)
    html = re.sub(r"<div\b[^>]*>", "<p>", html, flags=re.S | re.I)
    html = re.sub(r"</div>", "</p>", html, flags=re.S | re.I)
    html = re.sub(
        r"<p\b[^>]*>",
        '<p style="margin:0 0 14px;line-height:1.95;text-align:justify;text-indent:2em;font-size:16px;color:#3f3f46;">',
        html,
        flags=re.S | re.I,
    )
    html = re.sub(r"<br\s*/?>", "<br/>", html, flags=re.S | re.I)
    html = re.sub(r"<(strong|b)\b[^>]*>", "<strong>", html, flags=re.S | re.I)
    html = re.sub(r"</(strong|b)>", "</strong>", html, flags=re.S | re.I)
    html = re.sub(r"<(em|i)\b[^>]*>", "<em>", html, flags=re.S | re.I)
    html = re.sub(r"</(em|i)>", "</em>", html, flags=re.S | re.I)
    html = re.sub(
        r"<a\b[^>]*href=(?P<quote>[\'\"])(?P<href>.*?)(?P=quote)[^>]*>",
        lambda m: f'<a href="{make_absolute_url(unescape(m.group("href")).strip())}" style="color:#2563eb;">',
        html,
        flags=re.S | re.I,
    )
    html = re.sub(r"<(?!/?(p|br|img|strong|em|a)\b)[^>]+>", "", html, flags=re.S | re.I)
    html = re.sub(r"<p[^>]*>\s*</p>", "", html, flags=re.S | re.I)
    html = re.sub(r"(?:<br/>\s*){3,}", "<br/><br/>", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r">\s+<", "><", html)
    return html


def build_notifications_payload(limit: int) -> dict:
    rows = get_latest_notifications(limit=limit)
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "newsId": row["news_id"],
                "title": row["title"] or "",
                "department": row["publish_department"] or "未知部门",
                "publishTime": format_datetime(row["publish_time"]),
                "summary": build_summary(row["content_text"]),
                "detailUrl": row["detail_url"] or "",
                "viewCount": int(row["view_count"] or 0),
                "unread": False,
            }
        )

    return {
        "items": items,
        "totalCount": get_notifications_total_count(),
        "unreadCount": 0,
        "lastSync": datetime.now().strftime("%H:%M"),
    }


def build_undergraduate_notifications_payload(limit: int) -> dict:
    rows = get_undergraduate_notifications(limit=limit)
    return build_audience_notifications_payload_from_rows(rows)


def build_audience_notifications_payload(audience_type: str, limit: int) -> dict:
    rows = get_notifications_by_audience_type(audience_type, limit=limit)
    return build_audience_notifications_payload_from_rows(rows)


def build_audience_notifications_payload_from_rows(rows: list[dict]) -> dict:
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "newsId": row["news_id"],
                "title": row["title"] or "",
                "department": row["publish_department"] or "未知部门",
                "publishTime": format_datetime(row["publish_time"]),
                "category": row["category"] or "",
                "summary": build_summary(row["content_text"]),
                "detailUrl": row["detail_url"] or "",
                "ruleVersion": row.get("audience_rule_version") or "",
                "ruleDetail": row.get("audience_rule_detail") or "",
            }
        )
    return {
        "items": items,
        "totalCount": len(items),
        "lastSync": datetime.now().strftime("%H:%M"),
    }


def build_notification_detail_payload(news_id: str) -> dict | None:
    row = get_notification_by_news_id(news_id)
    if not row:
        return None

    attachments = []
    for item in get_attachments_by_news_id(news_id):
        attachments.append(
            {
                "fileId": item["file_id"],
                "filename": item["filename"] or "未命名附件",
                "extension": item["extension"] or "",
                "size": int(item["size"] or 0),
            }
        )

    return {
        "id": row["id"],
        "newsId": row["news_id"],
        "title": row["title"] or "",
        "department": row["publish_department"] or "未知部门",
        "publishTime": format_datetime(row["publish_time"]),
        "category": row["category"] or "",
        "contentText": row["content_text"] or "",
        "contentHtml": row["content_html"] or "",
        "miniappContentHtml": build_miniapp_content_html(row.get("content_html")),
        "detailUrl": row["detail_url"] or "",
        "viewCount": int(row["view_count"] or 0),
        "images": extract_image_urls(row.get("content_html")),
        "attachments": attachments,
    }


def build_reminders_payload(user_email: str, limit: int) -> dict:
    ensure_miniapp_delivery_records_for_user(user_email, limit=max(limit, 20))
    rows = get_miniapp_delivery_rows(user_email, limit=limit)
    items = []
    unread_count = 0
    for row in rows:
        is_read = str(row.get("status") or "").lower() == "read"
        if not is_read:
            unread_count += 1
        items.append(
            {
                "deliveryId": int(row["delivery_id"]),
                "newsId": row["news_id"],
                "title": row["title"] or "",
                "department": row["publish_department"] or "未知部门",
                "publishTime": format_datetime(row["publish_time"]),
                "detailUrl": row["detail_url"] or "",
                "summary": build_summary(row.get("content_text")),
                "isRead": is_read,
                "status": row.get("status") or "pending",
            }
        )
    return {
        "items": items,
        "totalCount": len(items),
        "unreadCount": unread_count,
        "lastSync": datetime.now().strftime("%H:%M"),
        "userEmail": user_email,
    }


def build_subscribe_status_payload(user_email: str) -> dict:
    user = get_user_by_email(user_email)
    return {
        "userEmail": user_email,
        "miniappEnabled": config.WECHAT_MINIAPP_ENABLED,
        "serverConfigured": miniapp_is_configured(),
        "templateId": config.WECHAT_SUBSCRIBE_TEMPLATE_ID,
        "subscribePage": config.WECHAT_SUBSCRIBE_PAGE,
        "hasBoundUser": bool(user),
        "hasWechatOpenid": bool(user and user.get("wechat_openid")),
        "wechatOpenidMasked": mask_openid(user.get("wechat_openid") if user else ""),
    }


def build_department_subscriptions_payload(user_email: str) -> dict:
    rows = get_user_department_subscriptions(user_email)
    items = []
    for row in rows:
        items.append(
            {
                "department": row.get("target_value") or "",
                "status": int(row.get("status") or 0),
            }
        )
    return {
        "userEmail": user_email,
        "items": items,
        "departments": [item["department"] for item in items if item["department"]],
    }


def build_user_settings_payload(user_email: str) -> dict:
    settings = get_user_notification_settings(user_email)
    if not settings:
        ensure_demo_miniapp_user(user_email, username=user_email.split("@")[0] or "miniapp_user")
        settings = get_user_notification_settings(user_email)

    return {
        "userEmail": user_email,
        "emailEnabled": bool((settings or {}).get("email_notifications_enabled", 1)),
        "miniappEnabled": bool((settings or {}).get("miniapp_notifications_enabled", 1)),
        "refreshIntervalMinutes": int((settings or {}).get("notification_refresh_interval_minutes") or 60),
        "lastNotificationCheckAt": format_datetime((settings or {}).get("last_notification_check_at")),
        "hasUser": bool(settings),
    }


def build_admin_crawler_config_payload() -> dict:
    runtime_config = get_crawler_runtime_config()
    return {
        "schedulerEnabled": bool(runtime_config["SCHEDULER_ENABLED"]["value"]),
        "schedulerIntervalMinutes": float(runtime_config["SCHEDULER_INTERVAL_MINUTES"]["value"]),
        "schedulerMaxRuns": int(runtime_config["SCHEDULER_MAX_RUNS"]["value"]),
        "maxRecords": int(runtime_config["MAX_RECORDS"]["value"]),
        "requestDelayMin": float(runtime_config["REQUEST_DELAY_MIN"]["value"]),
        "requestDelayMax": float(runtime_config["REQUEST_DELAY_MAX"]["value"]),
        "updatedKeys": sorted(runtime_config.keys()),
    }


def build_admin_crawler_jobs_payload(limit: int, page: int) -> dict:
    offset = max(page - 1, 0) * limit
    rows = get_crawl_job_logs(limit=limit, offset=offset)
    total_count = get_crawl_job_logs_total_count()
    items = []
    for row in rows:
        items.append(
            {
                "id": int(row["id"]),
                "jobType": row.get("job_type") or "",
                "triggerMode": row.get("trigger_mode") or "",
                "status": row.get("status") or "",
                "startedAt": format_datetime(row.get("started_at")),
                "finishedAt": format_datetime(row.get("finished_at")),
                "durationSeconds": int(row.get("duration_seconds") or 0),
                "notificationsCount": int(row.get("notifications_count") or 0),
                "attachmentsCount": int(row.get("attachments_count") or 0),
                "dbNotificationsCount": int(row.get("db_notifications_count") or 0),
                "dbAttachmentsCount": int(row.get("db_attachments_count") or 0),
                "message": row.get("message") or "",
                "errorMessage": row.get("error_message") or "",
            }
        )
    return {
        "items": items,
        "page": page,
        "pageSize": limit,
        "totalCount": total_count,
        "hasMore": offset + len(items) < total_count,
        "runState": ADMIN_CRAWLER_RUN_STATE,
    }


def build_admin_crawler_job_detail_payload(job_id: int) -> dict | None:
    row = get_crawl_job_log_by_id(job_id)
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "jobType": row.get("job_type") or "",
        "triggerMode": row.get("trigger_mode") or "",
        "status": row.get("status") or "",
        "incrementalMode": int(row.get("incremental_mode") or 0),
        "schedulerEnabled": bool(row.get("scheduler_enabled")),
        "intervalHours": row.get("interval_hours"),
        "startedAt": format_datetime(row.get("started_at")),
        "finishedAt": format_datetime(row.get("finished_at")),
        "durationSeconds": int(row.get("duration_seconds") or 0),
        "notificationsCount": int(row.get("notifications_count") or 0),
        "attachmentsCount": int(row.get("attachments_count") or 0),
        "dbNotificationsCount": int(row.get("db_notifications_count") or 0),
        "dbAttachmentsCount": int(row.get("db_attachments_count") or 0),
        "message": row.get("message") or "",
        "errorMessage": row.get("error_message") or "",
        "createdAt": format_datetime(row.get("created_at")),
        "updatedAt": format_datetime(row.get("updated_at")),
    }


def run_crawler_once_in_background() -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ADMIN_CRAWLER_RUN_STATE.update(
        {
            "running": True,
            "lastStartedAt": started_at,
            "lastFinishedAt": "",
            "lastStatus": "running",
            "lastMessage": "Crawler run started from admin API",
        }
    )
    try:
        apply_crawler_runtime_config()
        run_crawler_once()
        ADMIN_CRAWLER_RUN_STATE.update(
            {
                "running": False,
                "lastFinishedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastStatus": "success",
                "lastMessage": "Crawler run completed successfully",
            }
        )
    except Exception as exc:
        LOGGER.exception("Admin crawler run failed")
        ADMIN_CRAWLER_RUN_STATE.update(
            {
                "running": False,
                "lastFinishedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastStatus": "failed",
                "lastMessage": str(exc),
            }
        )


def mask_openid(openid: str | None) -> str:
    clean = str(openid or "").strip()
    if len(clean) <= 10:
        return clean
    return f"{clean[:4]}***{clean[-4:]}"


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        return {}
    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


class NotificationApiHandler(BaseHTTPRequestHandler):
    server_version = "OANotificationAPI/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            self.write_json(200, {"code": 0, "message": "ok"})
            return

        if parsed.path == "/api/notifications":
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            payload = build_notifications_payload(limit)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/notifications/undergraduate":
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            payload = build_undergraduate_notifications_payload(limit)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/notifications/graduate":
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            payload = build_audience_notifications_payload("graduate", limit)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/notifications/staff":
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            payload = build_audience_notifications_payload("staff", limit)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/notification-detail":
            news_id = (query.get("newsId", [""])[0] or "").strip()
            if not news_id:
                self.write_json(400, {"code": 400, "message": "missing newsId"})
                return
            payload = build_notification_detail_payload(news_id)
            if not payload:
                self.write_json(404, {"code": 404, "message": "notification not found"})
                return
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/reminders":
            user_email = (query.get("userEmail", [""])[0] or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            payload = build_reminders_payload(user_email, limit)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/reminders/read":
            user_email = (query.get("userEmail", [""])[0] or "").strip()
            raw_ids = (query.get("deliveryIds", [""])[0] or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            delivery_ids = [int(item) for item in raw_ids.split(",") if item.strip().isdigit()]
            affected = mark_miniapp_deliveries_read(user_email, delivery_ids)
            self.write_json(200, {"code": 0, "message": "success", "data": {"updated": affected}})
            return

        if parsed.path == "/api/miniapp/subscribe/status":
            user_email = (query.get("userEmail", [""])[0] or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            payload = build_subscribe_status_payload(user_email)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/subscriptions/departments":
            user_email = (query.get("userEmail", [""])[0] or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            payload = build_department_subscriptions_payload(user_email)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/users/settings":
            user_email = (query.get("userEmail", [""])[0] or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            payload = build_user_settings_payload(user_email)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/admin/crawler/config":
            payload = build_admin_crawler_config_payload()
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/admin/crawler/jobs":
            limit = self.parse_limit(query.get("limit", ["20"])[0])
            page = self.parse_page(query.get("page", ["1"])[0])
            payload = build_admin_crawler_jobs_payload(limit, page)
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/admin/crawler/job-detail":
            raw_job_id = (query.get("jobId", [""])[0] or "").strip()
            if not raw_job_id.isdigit():
                self.write_json(400, {"code": 400, "message": "invalid jobId"})
                return
            payload = build_admin_crawler_job_detail_payload(int(raw_job_id))
            if not payload:
                self.write_json(404, {"code": 404, "message": "job not found"})
                return
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        self.write_json(404, {"code": 404, "message": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = parse_json_body(self)

        if parsed.path == "/api/miniapp/session":
            user_email = str(body.get("userEmail") or "").strip()
            code = str(body.get("code") or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            if not code:
                self.write_json(400, {"code": 400, "message": "missing code"})
                return
            try:
                ensure_demo_miniapp_user(user_email, username=user_email.split("@")[0] or "miniapp_user")
                session_info = exchange_code_for_openid(code)
                openid = str(session_info.get("openid") or "").strip()
                if not openid:
                    self.write_json(500, {"code": 500, "message": "openid empty"})
                    return
                update_user_wechat_openid(user_email, openid)
                payload = build_subscribe_status_payload(user_email)
                payload["sessionBound"] = True
                self.write_json(200, {"code": 0, "message": "success", "data": payload})
                return
            except MiniappNotifierError as exc:
                self.write_json(500, {"code": 500, "message": str(exc)})
                return

        if parsed.path == "/api/miniapp/send-test":
            user_email = str(body.get("userEmail") or "").strip()
            news_id = str(body.get("newsId") or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            if not news_id:
                self.write_json(400, {"code": 400, "message": "missing newsId"})
                return

            user = get_user_by_email(user_email)
            if not user:
                self.write_json(404, {"code": 404, "message": "user not found"})
                return
            openid = str(user.get("wechat_openid") or "").strip()
            if not openid:
                self.write_json(400, {"code": 400, "message": "user wechat_openid not bound"})
                return
            notification = get_notification_by_news_id(news_id)
            if not notification:
                self.write_json(404, {"code": 404, "message": "notification not found"})
                return

            try:
                ensure_miniapp_delivery_records_for_user(user_email, limit=20)
                delivery_ids = get_miniapp_delivery_ids_by_user_and_news(user_email, news_id)
                response = send_subscribe_message(
                    openid,
                    notification,
                    page=f"pages/detail/detail?newsId={news_id}",
                )
                if delivery_ids:
                    mark_delivery_success(delivery_ids, provider_message_id=str(response.get("msgid") or ""))
                self.write_json(
                    200,
                    {
                        "code": 0,
                        "message": "success",
                        "data": {
                            "userEmail": user_email,
                            "newsId": news_id,
                            "openidMasked": mask_openid(openid),
                            "wechatResponse": response,
                        },
                    },
                )
                return
            except MiniappNotifierError as exc:
                delivery_ids = get_miniapp_delivery_ids_by_user_and_news(user_email, news_id)
                if delivery_ids:
                    mark_delivery_failed(delivery_ids, str(exc))
                self.write_json(500, {"code": 500, "message": str(exc)})
                return

        if parsed.path == "/api/subscriptions/department":
            user_email = str(body.get("userEmail") or "").strip()
            department = str(body.get("department") or "").strip()
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            if not department:
                self.write_json(400, {"code": 400, "message": "missing department"})
                return
            payload = upsert_department_subscription(
                user_email,
                department,
            )
            self.write_json(
                200,
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "department": payload.get("target_value") or department,
                        "status": int(payload.get("status") or 0),
                    },
                },
            )
            return

        if parsed.path == "/api/users/settings":
            user_email = str(body.get("userEmail") or "").strip()
            raw_interval = body.get("refreshIntervalMinutes")
            raw_email_enabled = body.get("emailEnabled")
            raw_miniapp_enabled = body.get("miniappEnabled")
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            refresh_interval_minutes = None
            if raw_interval is not None:
                if isinstance(raw_interval, str) and not raw_interval.strip():
                    raw_interval = None
            if raw_interval is not None:
                try:
                    refresh_interval_minutes = int(raw_interval)
                except (TypeError, ValueError):
                    self.write_json(400, {"code": 400, "message": "invalid refreshIntervalMinutes"})
                    return
            try:
                payload = upsert_user_notification_settings(
                    user_email,
                    refresh_interval_minutes=refresh_interval_minutes,
                    email_enabled=None if raw_email_enabled is None else bool(raw_email_enabled),
                    miniapp_enabled=None if raw_miniapp_enabled is None else bool(raw_miniapp_enabled),
                )
            except ValueError as exc:
                self.write_json(400, {"code": 400, "message": str(exc)})
                return

            self.write_json(
                200,
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "userEmail": payload.get("email") or user_email,
                        "emailEnabled": bool(payload.get("email_notifications_enabled", 1)),
                        "miniappEnabled": bool(payload.get("miniapp_notifications_enabled", 1)),
                        "refreshIntervalMinutes": int(payload.get("notification_refresh_interval_minutes") or 60),
                        "lastNotificationCheckAt": format_datetime(payload.get("last_notification_check_at")),
                    },
                },
            )
            return

        if parsed.path == "/api/subscriptions/batch":
            user_email = str(body.get("userEmail") or "").strip()
            subscriptions = body.get("subscriptions") or []
            if not user_email:
                self.write_json(400, {"code": 400, "message": "missing userEmail"})
                return
            if not isinstance(subscriptions, list):
                self.write_json(400, {"code": 400, "message": "subscriptions must be a list"})
                return
            try:
                rows = save_user_department_subscriptions(user_email, subscriptions)
            except ValueError as exc:
                self.write_json(400, {"code": 400, "message": str(exc)})
                return
            payload = {
                "userEmail": user_email,
                "items": [
                    {
                        "department": row.get("target_value") or "",
                        "status": int(row.get("status") or 0),
                    }
                    for row in rows
                ],
            }
            self.write_json(200, {"code": 0, "message": "success", "data": payload})
            return

        if parsed.path == "/api/admin/crawler/config":
            def parse_bool(value):
                if value is None:
                    return None
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("1", "true", "yes", "on")

            def parse_int(value, field_name: str):
                if value is None or value == "":
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"invalid {field_name}")

            def parse_float(value, field_name: str):
                if value is None or value == "":
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"invalid {field_name}")

            try:
                payload = update_crawler_runtime_config(
                    scheduler_enabled=parse_bool(body.get("schedulerEnabled")),
                    scheduler_interval_minutes=parse_float(body.get("schedulerIntervalMinutes"), "schedulerIntervalMinutes"),
                    scheduler_max_runs=parse_int(body.get("schedulerMaxRuns"), "schedulerMaxRuns"),
                    max_records=parse_int(body.get("maxRecords"), "maxRecords"),
                    request_delay_min=parse_float(body.get("requestDelayMin"), "requestDelayMin"),
                    request_delay_max=parse_float(body.get("requestDelayMax"), "requestDelayMax"),
                )
                apply_crawler_runtime_config()
            except ValueError as exc:
                self.write_json(400, {"code": 400, "message": str(exc)})
                return

            self.write_json(
                200,
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "schedulerEnabled": bool(payload["SCHEDULER_ENABLED"]["value"]),
                        "schedulerIntervalMinutes": float(payload["SCHEDULER_INTERVAL_MINUTES"]["value"]),
                        "schedulerMaxRuns": int(payload["SCHEDULER_MAX_RUNS"]["value"]),
                        "maxRecords": int(payload["MAX_RECORDS"]["value"]),
                        "requestDelayMin": float(payload["REQUEST_DELAY_MIN"]["value"]),
                        "requestDelayMax": float(payload["REQUEST_DELAY_MAX"]["value"]),
                    },
                },
            )
            return

        if parsed.path == "/api/admin/crawler/run":
            if ADMIN_CRAWLER_RUN_STATE["running"]:
                self.write_json(409, {"code": 409, "message": "crawler run already in progress"})
                return
            worker = threading.Thread(target=run_crawler_once_in_background, daemon=True)
            worker.start()
            self.write_json(
                200,
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "started": True,
                        "runState": ADMIN_CRAWLER_RUN_STATE,
                    },
                },
            )
            return

        self.write_json(404, {"code": 404, "message": "not found"})

    def parse_limit(self, raw_value: str) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return 20
        return min(max(value, 1), 50)

    def parse_page(self, raw_value: str) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return 1
        return max(value, 1)

    def write_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format: str, *args) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def main() -> None:
    setup_logging()
    LOGGER.info("Notification API server starting")
    initialize_schema()
    test_connection()
    apply_crawler_runtime_config()

    server = ThreadingHTTPServer((HOST, PORT), NotificationApiHandler)
    LOGGER.info("Notification API server started: http://127.0.0.1:%s", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Notification API server stopped by user")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
