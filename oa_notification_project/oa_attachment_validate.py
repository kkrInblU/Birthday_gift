import sys

from oa_crawler.crawler import OANotificationCrawler


def validate_attachment(news_id: str) -> int:
    crawler = OANotificationCrawler()
    crawler.initialize_session()
    detail_html = crawler.fetch_detail_html(news_id)
    attachments = crawler.parse_attachments(detail_html, news_id)

    if not attachments:
        print("No attachments found for news:", news_id)
        return 1

    print(f"Attachment count: {len(attachments)}")
    for index, item in enumerate(attachments, start=1):
        print(f"\n[{index}] {item.get('filename')}")
        print("file_id   :", item.get("file_id"))
        print("extension :", item.get("extension"))
        print("size      :", item.get("size"))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python .\\oa_notification_project\\oa_attachment_validate.py <news_id>")
        return 1
    news_id = sys.argv[1].strip()
    if not news_id:
        print("news_id is required")
        return 1
    return validate_attachment(news_id)


if __name__ == "__main__":
    raise SystemExit(main())
