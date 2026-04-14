import logging
import smtplib
from email.message import EmailMessage

from oa_crawler import config
from oa_crawler.notifier import build_body, build_subject


LOGGER = logging.getLogger("oa_crawler")


def mail_is_configured() -> bool:
    return all(
        [
            config.MAIL_ENABLED,
            config.SMTP_HOST,
            config.SMTP_USER,
            config.SMTP_PASSWORD,
            config.MAIL_FROM,
        ]
    )


def build_notifications_email(recipient: str, notifications: list[dict]) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.MAIL_FROM
    message["To"] = recipient
    message["Subject"] = build_subject(notifications)
    message.set_content(build_body(notifications))
    return message


def send_notifications_email(recipient: str, notifications: list[dict]) -> bool:
    if not notifications:
        LOGGER.info("No new notifications, email will not be sent")
        return False
    if not mail_is_configured():
        LOGGER.info("Mail configuration incomplete or disabled, skipping email sending")
        return False
    if not recipient:
        LOGGER.info("Mail recipient is empty, skipping email sending")
        return False

    message = build_notifications_email(recipient, notifications)
    LOGGER.info("Sending notification email: recipient=%s, notifications=%s", recipient, len(notifications))

    if config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)

    LOGGER.info("Notification email sent successfully")
    return True


def send_new_notifications_email(new_notifications: list[dict]) -> bool:
    return send_notifications_email(config.MAIL_TO, new_notifications)
