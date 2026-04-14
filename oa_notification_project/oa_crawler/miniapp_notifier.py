import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from oa_crawler import config


LOGGER = logging.getLogger("oa_crawler")


class MiniappNotifierError(RuntimeError):
    pass


def miniapp_is_configured() -> bool:
    return all(
        [
            config.WECHAT_MINIAPP_ENABLED,
            config.WECHAT_MINIAPP_APPID,
            config.WECHAT_MINIAPP_SECRET,
            config.WECHAT_SUBSCRIBE_TEMPLATE_ID,
        ]
    )


def _http_get_json(url: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}"
    request = urllib.request.Request(
        request_url,
        headers={
            "User-Agent": config.DEFAULT_HEADERS["User-Agent"],
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise MiniappNotifierError(f"微信接口请求失败: {exc}") from exc


def _http_post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": config.DEFAULT_HEADERS["User-Agent"],
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise MiniappNotifierError(f"微信接口请求失败: {exc}") from exc


def get_access_token() -> str:
    if not miniapp_is_configured():
        raise MiniappNotifierError("微信小程序订阅消息配置未完成")

    payload = _http_get_json(
        config.WECHAT_ACCESS_TOKEN_URL,
        {
            "grant_type": "client_credential",
            "appid": config.WECHAT_MINIAPP_APPID,
            "secret": config.WECHAT_MINIAPP_SECRET,
        },
    )
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise MiniappNotifierError(
            f"获取 access_token 失败: errcode={payload.get('errcode')} errmsg={payload.get('errmsg')}"
        )
    return access_token


def exchange_code_for_openid(code: str) -> dict:
    clean_code = str(code or "").strip()
    if not clean_code:
        raise MiniappNotifierError("缺少 wx.login code")
    if not miniapp_is_configured():
        raise MiniappNotifierError("微信小程序订阅消息配置未完成")

    payload = _http_get_json(
        config.WECHAT_CODE2SESSION_URL,
        {
            "appid": config.WECHAT_MINIAPP_APPID,
            "secret": config.WECHAT_MINIAPP_SECRET,
            "js_code": clean_code,
            "grant_type": "authorization_code",
        },
    )
    openid = str(payload.get("openid") or "").strip()
    if not openid:
        raise MiniappNotifierError(
            f"code2Session 失败: errcode={payload.get('errcode')} errmsg={payload.get('errmsg')}"
        )
    return payload


def build_template_data(notification: dict) -> dict:
    mapping = config.WECHAT_TEMPLATE_DATA_MAPPING or {}
    summary = str(notification.get("content_text") or "").strip().replace("\r", " ").replace("\n", " ")
    if len(summary) > 20:
        summary = summary[:20]
    values = {
        "title": str(notification.get("title") or "校园通知")[:20],
        "department": str(notification.get("publish_department") or notification.get("category") or "OA系统")[:20],
        "publish_time": _format_publish_time(notification.get("publish_time")),
        "detail_url": str(notification.get("detail_url") or ""),
        "category": str(notification.get("category") or "通知消息")[:20],
        "summary": summary or str(notification.get("title") or "你有一条新的校园通知")[:20],
    }
    data = {}
    for key, template in mapping.items():
        rendered = str(template or "").format(**values)
        clean_value = rendered.strip()[:100]
        if not clean_value:
            if "time" in str(key).lower():
                clean_value = values["publish_time"] or datetime.now().strftime("%Y-%m-%d %H:%M")
            elif str(key) == "thing31":
                clean_value = values["department"] or "OA系统"
            elif str(key) == "thing30":
                clean_value = values["title"] or "校园通知"
            elif str(key) == "thing2":
                clean_value = values["summary"] or "你有一条新的校园通知"
            else:
                clean_value = "校园通知"
        data[str(key)] = {"value": clean_value}
    return data


def _format_publish_time(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)[:20]


def send_subscribe_message(openid: str, notification: dict, *, page: str | None = None) -> dict:
    clean_openid = str(openid or "").strip()
    if not clean_openid:
        raise MiniappNotifierError("用户 openid 为空，无法发送订阅消息")
    access_token = get_access_token()
    page_path = str(page or config.WECHAT_SUBSCRIBE_PAGE).strip() or "pages/index/index"
    request_url = f"{config.WECHAT_SUBSCRIBE_SEND_URL}?access_token={urllib.parse.quote(access_token)}"
    payload = {
        "touser": clean_openid,
        "template_id": config.WECHAT_SUBSCRIBE_TEMPLATE_ID,
        "page": page_path,
        "miniprogram_state": config.WECHAT_SUBSCRIBE_MINIPROGRAM_STATE,
        "lang": config.WECHAT_SUBSCRIBE_LANG,
        "data": build_template_data(notification),
    }
    LOGGER.info(
        "Miniapp subscribe payload: news_id=%s, publish_department=%s, category=%s, payload_data=%s",
        notification.get("news_id"),
        notification.get("publish_department"),
        notification.get("category"),
        json.dumps(payload["data"], ensure_ascii=False),
    )
    response = _http_post_json(request_url, payload)
    errcode = int(response.get("errcode") or 0)
    if errcode != 0:
        raise MiniappNotifierError(
            f"发送订阅消息失败: errcode={response.get('errcode')} errmsg={response.get('errmsg')}"
        )
    LOGGER.info("Miniapp subscribe message sent successfully: openid=%s", clean_openid)
    return response
