import json
import logging
import random
import re
import time
from ast import literal_eval
from datetime import datetime
from http.cookiejar import CookieJar
from html import unescape
from html.parser import HTMLParser
from typing import Callable, Dict, List, Tuple
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from oa_crawler import config


LOGGER = logging.getLogger("oa_crawler")


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


class OANotificationCrawler:
    def __init__(self, existing_news_lookup: Callable[[List[str]], set[str]] | None = None) -> None:
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        self.session_initialized = False
        self.request_count = 0
        self.notifications: List[Dict] = []
        self.attachments: List[Dict] = []
        self.existing_news_lookup = existing_news_lookup
        self.incremental_stop_requested = False
        LOGGER.info("Crawler initialized")

    def fetch_text(self, url: str, data: bytes | None = None, headers: Dict[str, str] | None = None) -> str:
        method = "POST" if data else "GET"
        self.pause_between_requests()
        LOGGER.info("HTTP %s -> %s", method, url)
        request = Request(url=url, data=data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=config.TIMEOUT) as response:
                content_type = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(content_type, errors="replace")
                self.request_count += 1
                LOGGER.info("HTTP %s success <- %s", method, url)
                return text
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            LOGGER.error("HTTP %s failed <- %s, status=%s", method, url, exc.code)
            raise RuntimeError(f"HTTP {exc.code} for {url}\n{error_body[:1000]}") from exc

    def build_list_payload(self, fragment_id: str, page_no: int) -> bytes:
        arguments = [
            {
                "pageSize": str(config.PAGE_SIZE),
                "pageNo": page_no,
                "listType": "1",
                "spaceType": "2",
                "spaceId": "",
                "typeId": "",
                "condition": "publishDepartment",
                "textfield1": "",
                "textfield2": "",
                "myNews": "",
                "fragmentId": fragment_id,
                "ordinal": "0",
                "panelValue": "designated_value",
            }
        ]
        payload = {
            "managerMethod": "findListDatas",
            "arguments": json.dumps(arguments, ensure_ascii=False),
        }
        return urlencode(payload).encode("utf-8")

    def fetch_list_page(self, fragment_id: str, page_no: int) -> Dict:
        LOGGER.info("Fetching list page: fragment_id=%s, page_no=%s", fragment_id, page_no)
        if not self.session_initialized:
            self.initialize_session()
        list_page_url = (
            f"{config.BASE_URL}{config.SEEYON_PATH}/newsData.do?method=newsIndex"
            f"&spaceType=2&fragmentId={fragment_id}&ordinal=0&panelValue=designated_value"
        )
        self.fetch_text(list_page_url, headers=config.DETAIL_HEADERS)
        LOGGER.info("List page HTML loaded: fragment_id=%s, page_no=%s", fragment_id, page_no)
        api_url = f"{config.LIST_API_URL}&rnd={random.randint(10000, 99999)}"
        response_text = self.fetch_text(
            api_url,
            data=self.build_list_payload(fragment_id, page_no),
            headers={
                **config.LIST_HEADERS,
                "Referer": list_page_url,
                "Origin": config.BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        result = json.loads(response_text)
        LOGGER.info(
            "List API success: fragment_id=%s, page_no=%s, items=%s, total_pages=%s",
            fragment_id,
            page_no,
            len(result.get("list", [])),
            result.get("pages", 0),
        )
        return result

    def initialize_session(self) -> None:
        LOGGER.info("Initializing session")
        self.fetch_text(config.PORTAL_HOME_URL, headers=config.DETAIL_HEADERS)
        self.session_initialized = True
        LOGGER.info("Session initialized")

    def build_detail_url(self, news_id: str) -> str:
        return config.DETAIL_URL_TEMPLATE.format(news_id=news_id)

    def clean_detail_url(self, news_id: str) -> str:
        return self.build_detail_url(news_id)

    def fetch_detail_html(self, news_id: str) -> str:
        LOGGER.info("Fetching detail page: news_id=%s", news_id)
        html = self.fetch_text(self.build_detail_url(news_id), headers=config.DETAIL_HEADERS)
        LOGGER.info("Detail page loaded: news_id=%s", news_id)
        return html

    def parse_detail_meta(self, html: str) -> Dict[str, str]:
        meta = {
            "title": "",
            "publish_time": "",
            "publish_department": "",
            "category": "",
            "content_html": "",
            "content_text": "",
        }
        title_match = re.search(r'<div class="title_name"[^>]*>(.*?)</div>', html, re.S)
        if title_match:
            meta["title"] = self.clean_text(title_match.group(1))

        head_match = re.search(r'<div class="mainText_head_msg">(.*?)</div>\s*<div class="setBtn"', html, re.S)
        if head_match:
            spans = re.findall(r"<span[^>]*>(.*?)</span>", head_match.group(1), re.S)
            clean_spans = [self.clean_text(s) for s in spans if self.clean_text(s)]
            if len(clean_spans) >= 1:
                meta["publish_time"] = clean_spans[0]
            if len(clean_spans) >= 2:
                meta["publish_department"] = clean_spans[1]
            if len(clean_spans) >= 3:
                meta["category"] = clean_spans[2]

        content_match = re.search(r"<div id ='htmlContentDiv'>(.*?)</div>\s*<script type=\"text/javascript\">", html, re.S)
        if not content_match:
            content_match = re.search(r'<div id="htmlContentDiv">(.*?)</div>\s*<script', html, re.S)
        if content_match:
            content_html = content_match.group(1).strip()
            meta["content_html"] = content_html
            meta["content_text"] = self.html_to_text(content_html)
        return meta

    def parse_attachments(self, html: str, news_id: str) -> List[Dict]:
        match = re.search(r'id="attFileDomain"[^>]*attsdata=\'(.*?)\'', html, re.S)
        if not match:
            LOGGER.info("No attachment container found: news_id=%s", news_id)
            return []
        raw = unescape(match.group(1))
        raw = raw.strip()
        if not raw:
            LOGGER.info("Attachment data empty: news_id=%s", news_id)
            return []

        attachment_items = self.load_attachment_items(raw)
        if not attachment_items:
            LOGGER.warning("Attachment data parse failed or empty: news_id=%s", news_id)
            return []

        records = []
        for item in attachment_items:
            file_id = str(item.get("fileUrl", ""))
            filename = item.get("filename", "")
            records.append(
                {
                    "news_id": news_id,
                    "filename": filename,
                    "file_id": file_id,
                    "mime_type": item.get("mimeType", ""),
                    "extension": item.get("extension", ""),
                    "size": self.to_int(item.get("size")),
                    "can_browse": bool(item.get("canBrowse")),
                    "enable_online_view": bool(item.get("enableOnlineView")),
                    "sort": self.to_int(item.get("sort")),
                }
            )
        LOGGER.info("Attachments parsed: news_id=%s, count=%s", news_id, len(records))
        return records

    def load_attachment_items(self, raw: str) -> List[Dict]:
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass

        # Some pages return HTML-escaped JSON fragments or JS-style literals.
        cleaned = raw.replace("&quot;", '"').replace("&apos;", "'").strip()
        try:
            data = json.loads(cleaned)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            pass

        try:
            data = literal_eval(cleaned)
            return data if isinstance(data, list) else []
        except (ValueError, SyntaxError):
            return []

    def extract_image_urls(self, html: str) -> List[str]:
        urls: List[str] = []
        for match in re.finditer(r'<img[^>]+src=["\'](?P<src>[^"\']+)["\']', html, re.S | re.I):
            image_url = self.make_absolute_url(unescape(match.group("src")).strip())
            if image_url and image_url not in urls:
                urls.append(image_url)
        return urls

    def normalize_list_item(self, item: Dict, fragment_id: str, page_no: int) -> Dict:
        news_id = str(item.get("id", ""))
        return {
            "news_id": news_id,
            "title": item.get("title", ""),
            "publish_time": item.get("publishDate", ""),
            "publish_department": item.get("publishUserDepart", ""),
            "category": item.get("typeName", ""),
            "summary": item.get("content", ""),
            "content_html": "",
            "content_text": "",
            "has_image": bool(item.get("imageNews")),
            "image_url": self.make_absolute_url(item.get("imageUrl")),
            "has_attachments": bool(item.get("attachmentsFlag")),
            "attachment_count": 0,
            "detail_url": self.build_detail_url(news_id),
            "clean_detail_url": self.clean_detail_url(news_id),
            "type_id": item.get("typeId", ""),
            "type_name": item.get("typeName", ""),
            "publish_user_id": item.get("publishUserId", ""),
            "publish_user_name": item.get("publishUserName", ""),
            "read_count": self.to_int(item.get("readCount")),
            "reply_count": self.to_int(item.get("replyNumber")),
            "praise_count": self.to_int(item.get("praiseSum")),
            "fragment_id": fragment_id,
            "page_no": page_no,
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def fetch_notifications(self) -> Tuple[List[Dict], List[Dict]]:
        LOGGER.info("Fetch notifications started")
        self.notifications = []
        self.attachments = []
        self.incremental_stop_requested = False
        seen_news_ids = set()

        for fragment_name, fragment_id in config.FRAGMENTS.items():
            if self.reached_record_limit(self.notifications) or self.incremental_stop_requested:
                LOGGER.info("Record limit reached before fragment start, stopping crawl")
                break
            LOGGER.info("Processing fragment: %s (%s)", fragment_name, fragment_id)
            first_page = self.fetch_list_page(fragment_id, 1)
            total_pages = self.to_int(first_page.get("pages", 1))
            self.notifications, self.attachments = self.process_page(
                first_page, fragment_id, 1, self.notifications, self.attachments, seen_news_ids
            )
            if self.reached_record_limit(self.notifications) or self.incremental_stop_requested:
                LOGGER.info("Record limit reached after page: fragment_id=%s, page_no=1", fragment_id)
                break

            for page_no in range(2, total_pages + 1):
                if self.reached_record_limit(self.notifications) or self.incremental_stop_requested:
                    LOGGER.info("Record limit reached before next page, stopping crawl")
                    break
                page_data = self.fetch_list_page(fragment_id, page_no)
                self.notifications, self.attachments = self.process_page(
                    page_data, fragment_id, page_no, self.notifications, self.attachments, seen_news_ids
                )
                if self.reached_record_limit(self.notifications) or self.incremental_stop_requested:
                    LOGGER.info("Record limit reached after page: fragment_id=%s, page_no=%s", fragment_id, page_no)
                    break

        LOGGER.info(
            "Fetch notifications finished: notifications=%s, attachments=%s",
            len(self.notifications),
            len(self.attachments),
        )
        return self.notifications, self.attachments

    def process_page(
        self,
        page_data: Dict,
        fragment_id: str,
        page_no: int,
        notifications: List[Dict],
        attachments: List[Dict],
        seen_news_ids: set,
    ) -> Tuple[List[Dict], List[Dict]]:
        existing_news_ids = self.lookup_existing_news_ids(page_data)
        for item in page_data.get("list", []):
            if self.reached_record_limit(notifications) or self.incremental_stop_requested:
                LOGGER.info("Record limit reached inside page processing, stopping page loop")
                break
            record = self.normalize_list_item(item, fragment_id, page_no)
            news_id = record["news_id"]
            if not news_id or news_id in seen_news_ids:
                LOGGER.info("Skipping duplicate or empty news_id: %s", news_id)
                continue
            if self.is_incremental_enabled() and news_id in existing_news_ids:
                LOGGER.info("Existing news_id detected in database, stopping incremental crawl: %s", news_id)
                self.incremental_stop_requested = True
                break

            LOGGER.info("Processing record: news_id=%s, title=%s", news_id, record["title"])
            detail_html = self.fetch_detail_html(news_id)
            detail_meta = self.parse_detail_meta(detail_html)
            record["title"] = detail_meta.get("title") or record["title"]
            record["publish_time"] = detail_meta.get("publish_time") or record["publish_time"]
            record["publish_department"] = detail_meta.get("publish_department") or record["publish_department"]
            record["category"] = detail_meta.get("category") or record["category"]
            record["content_html"] = detail_meta.get("content_html", "")
            record["content_text"] = detail_meta.get("content_text", "")

            current_attachments = self.parse_attachments(detail_html, news_id)
            record["attachment_count"] = len(current_attachments)
            record["has_attachments"] = len(current_attachments) > 0

            notifications.append(record)
            attachments.extend(current_attachments)
            seen_news_ids.add(news_id)
            LOGGER.info(
                "Record completed: news_id=%s, attachments=%s",
                news_id,
                len(current_attachments),
            )
        return notifications, attachments

    def reached_record_limit(self, notifications: List[Dict]) -> bool:
        if config.MAX_RECORDS <= 0:
            return False
        return len(notifications) >= config.MAX_RECORDS

    def lookup_existing_news_ids(self, page_data: Dict) -> set[str]:
        if not self.is_incremental_enabled() or self.existing_news_lookup is None:
            return set()
        page_news_ids = [str(item.get("id", "")).strip() for item in page_data.get("list", []) if str(item.get("id", "")).strip()]
        if not page_news_ids:
            return set()
        existing_ids = self.existing_news_lookup(page_news_ids)
        if existing_ids:
            LOGGER.info("Existing news ids found in current page: count=%s", len(existing_ids))
        return existing_ids

    def is_incremental_enabled(self) -> bool:
        return int(config.INCREMENTAL_CRAWL_ENABLED) == 1

    def pause_between_requests(self) -> None:
        if self.request_count == 0:
            return
        delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
        LOGGER.info("Request pause: %.2fs", delay)
        time.sleep(delay)

    def make_absolute_url(self, path: str | None) -> str:
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return f"{config.BASE_URL}{path}"

    def clean_text(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def html_to_text(self, html: str) -> str:
        parser = TextExtractor()
        parser.feed(html)
        return parser.get_text()

    def to_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
