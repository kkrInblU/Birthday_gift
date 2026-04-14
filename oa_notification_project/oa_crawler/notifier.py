from oa_crawler import config


def build_subject(new_notifications: list[dict]) -> str:
    count = len(new_notifications)
    subject = config.MAIL_SUBJECT_TEMPLATE.format(count=count)
    prefix = config.MAIL_SUBJECT_PREFIX.strip()
    if prefix and prefix not in subject:
        return f"{prefix} {subject}"
    return subject


def build_body(new_notifications: list[dict]) -> str:
    lines = []
    count = len(new_notifications)
    lines.append(f"【校园通知更新】| 本次发现 {count} 条新通知")
    lines.append("")
    lines.append("---")
    lines.append("")

    for index, item in enumerate(new_notifications, start=1):
        lines.append(f"{index}.")
        lines.append(f"【标题】: {item.get('title', '')}")
        lines.append(f"【发布单位】: {item.get('publish_department', '')}")
        lines.append(f"【发布时间】: {item.get('publish_time', '')}")
        lines.append(f"【原文链接】: {item.get('detail_url', '')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("--")
    lines.append("此邮件由 [校园通知信息汇聚系统] 自动发送")
    return "\n".join(lines)
