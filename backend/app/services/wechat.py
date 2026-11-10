"""微信服务端接口：登录换 openid、access_token、订阅消息。"""
import logging
import time

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_token_cache: dict[str, float | str] = {}


class WechatError(Exception):
    pass


def code2session(code: str) -> dict:
    s = get_settings()
    if not s.wx_secret:
        # 本地开发没有 AppSecret 时，用 code 生成一个稳定的假 openid
        if s.env == "dev":
            return {"openid": f"dev_{code}", "unionid": None}
        raise WechatError("未配置 WX_SECRET")
    resp = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={"appid": s.wx_appid, "secret": s.wx_secret, "js_code": code, "grant_type": "authorization_code"},
        timeout=10,
    )
    data = resp.json()
    if data.get("errcode"):
        raise WechatError(f"code2Session 失败：{data.get('errcode')} {data.get('errmsg')}")
    return {"openid": data["openid"], "unionid": data.get("unionid")}


def access_token() -> str:
    s = get_settings()
    if _token_cache.get("token") and float(_token_cache.get("exp", 0)) > time.time() + 60:
        return str(_token_cache["token"])
    resp = httpx.post(
        "https://api.weixin.qq.com/cgi-bin/stable_token",
        json={"grant_type": "client_credential", "appid": s.wx_appid, "secret": s.wx_secret},
        timeout=10,
    )
    data = resp.json()
    if "access_token" not in data:
        raise WechatError(f"获取 access_token 失败：{data}")
    _token_cache["token"] = data["access_token"]
    _token_cache["exp"] = time.time() + int(data.get("expires_in", 7200))
    return data["access_token"]


def send_subscribe_message(openid: str, template_id: str, page: str, data: dict[str, str]) -> bool:
    """发送一次性订阅消息。返回是否成功；用户未授权（43101）返回 False。"""
    s = get_settings()
    body = {
        "touser": openid,
        "template_id": template_id,
        "page": page,
        "miniprogram_state": s.wx_miniprogram_state,
        "lang": "zh_CN",
        "data": {k: {"value": v} for k, v in data.items()},
    }
    resp = httpx.post(
        "https://api.weixin.qq.com/cgi-bin/message/subscribe/send",
        params={"access_token": access_token()},
        json=body,
        timeout=10,
    )
    result = resp.json()
    if result.get("errcode", 0) != 0:
        log.warning("订阅消息发送失败 openid=%s: %s", openid, result)
        return False
    return True
