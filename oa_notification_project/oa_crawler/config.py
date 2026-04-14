import os
import json
from pathlib import Path


BASE_URL = "https://oas.gdut.edu.cn"
SEEYON_PATH = "/seeyon"

LIST_API_URL = f"{BASE_URL}{SEEYON_PATH}/ajax.do?method=ajaxAction&managerName=newsDataManager"
PORTAL_HOME_URL = f"{BASE_URL}{SEEYON_PATH}/"
DETAIL_URL_TEMPLATE = f"{BASE_URL}{SEEYON_PATH}/newsData.do?method=newsView&newsId={{news_id}}"
ATTACHMENT_DOWNLOAD_URL = f"{BASE_URL}{SEEYON_PATH}/fileDownload.do?method=doDownload"

FRAGMENTS = {
    "latest_notice": "5854888065150372255",
    "latest_brief": "5821359576359193913",
    "latest_announcement": "-4899485396563308862",
}

FRAGMENT_LABELS = {
    "latest_notice": "最新通知",
    "latest_brief": "最新简讯",
    "latest_announcement": "最新公告",
}

PAGE_SIZE = 20
TIMEOUT = 20
MAX_RECORDS = int(os.getenv("OA_MAX_RECORDS", "10"))
REQUEST_DELAY_MIN = 0.8
REQUEST_DELAY_MAX = 1.6

# 0=关闭增量 1=开启增量
INCREMENTAL_CRAWL_ENABLED = 0

SCHEDULER_ENABLED = False
SCHEDULER_INTERVAL_MINUTES = 0.5
SCHEDULER_MAX_RUNS = 3

OUTPUT_DIR = Path("oa_crawler_output")
OUTPUT_FILE = OUTPUT_DIR / "notifications.xlsx"

DB_HOST = os.getenv("OA_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("OA_DB_PORT", "3306"))
DB_NAME = os.getenv("OA_DB_NAME", "oa_notifications")
DB_USER = os.getenv("OA_DB_USER", "root")
DB_PASSWORD = os.getenv("OA_DB_PASSWORD", "1234")
DB_CHARSET = os.getenv("OA_DB_CHARSET", "utf8mb4")
DB_CONNECT_TIMEOUT = int(os.getenv("OA_DB_CONNECT_TIMEOUT", "10"))

MAIL_ENABLED = os.getenv("OA_MAIL_ENABLED", "1") == "1"
SMTP_HOST = os.getenv("OA_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("OA_SMTP_PORT", "465"))
SMTP_USER = os.getenv("OA_SMTP_USER", "3307180168@qq.com")
SMTP_PASSWORD = os.getenv("OA_SMTP_PASSWORD", "swjruwbtxdbncjba")
SMTP_USE_SSL = os.getenv("OA_SMTP_USE_SSL", "1") == "1"
MAIL_FROM = os.getenv("OA_MAIL_FROM", "3307180168@qq.com")
MAIL_TO = os.getenv("OA_MAIL_TO", "3307180168@qq.com")
MAIL_SUBJECT_PREFIX = os.getenv("OA_MAIL_SUBJECT_PREFIX", "[校园通知提醒]")
MAIL_SUBJECT_TEMPLATE = os.getenv(
    "OA_MAIL_SUBJECT_TEMPLATE",
    "【校园通知更新】| 本次发现 {count} 条新通知",
)

WECHAT_MINIAPP_ENABLED = os.getenv("OA_WECHAT_MINIAPP_ENABLED", "1") == "1"
WECHAT_MINIAPP_APPID = os.getenv("OA_WECHAT_MINIAPP_APPID", "wxb5248d4348954996")
WECHAT_MINIAPP_SECRET = os.getenv("OA_WECHAT_MINIAPP_SECRET", "d1d2127a85fad62b7fecb077e6a68546")
WECHAT_SUBSCRIBE_TEMPLATE_ID = os.getenv(
    "OA_WECHAT_SUBSCRIBE_TEMPLATE_ID",
    "5qMeWCpdAQbiGQRiG9vcksyy6s37DFmSebSKDHddgHs",
)
WECHAT_SUBSCRIBE_PAGE = os.getenv("OA_WECHAT_SUBSCRIBE_PAGE", "pages/index/index")
WECHAT_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
WECHAT_SUBSCRIBE_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
WECHAT_SUBSCRIBE_MINIPROGRAM_STATE = os.getenv("OA_WECHAT_SUBSCRIBE_MINIPROGRAM_STATE", "developer")
WECHAT_SUBSCRIBE_LANG = os.getenv("OA_WECHAT_SUBSCRIBE_LANG", "zh_CN")
WECHAT_TEMPLATE_DATA_MAPPING = json.loads(
    os.getenv(
        "OA_WECHAT_TEMPLATE_DATA_MAPPING",
        '{"thing31":"{department}","thing30":"{title}","thing2":"{summary}","time3":"{publish_time}"}',
    )
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

LIST_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Origin": BASE_URL,
    "RequestType": "AJAX",
}

DETAIL_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NOTIFICATION_COLUMNS = [
    "news_id",
    "title",
    "publish_time",
    "publish_department",
    "category",
    "summary",
    "content_html",
    "content_text",
    "has_image",
    "image_url",
    "has_attachments",
    "attachment_count",
    "detail_url",
    "clean_detail_url",
    "type_id",
    "type_name",
    "publish_user_id",
    "publish_user_name",
    "read_count",
    "reply_count",
    "praise_count",
    "fragment_id",
    "page_no",
    "crawl_time",
]

ATTACHMENT_COLUMNS = [
    "news_id",
    "filename",
    "file_id",
    "mime_type",
    "extension",
    "size",
    "can_browse",
    "enable_online_view",
    "sort",
]
