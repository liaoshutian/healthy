"""OpenAI 兼容接口的最小客户端。ChatGPT、通义千问（DashScope 兼容模式）、DeepSeek 都走这一个。"""
import base64
import json
import re
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class Provider:
    name: str  # openai / qwen / deepseek
    base_url: str
    api_key: str
    model: str
    json_mode: bool = True  # 是否支持 response_format=json_object


class AIError(Exception):
    pass


def vision_providers() -> list[Provider]:
    """看图：主模型 ChatGPT，失败切到通义千问 VL。没配 key 的跳过。"""
    s = get_settings()
    providers = [
        Provider("openai", s.openai_base_url, s.openai_api_key, s.openai_vision_model, True),
        Provider("qwen", s.qwen_base_url, s.qwen_api_key, s.qwen_vision_model, False),
    ]
    return [p for p in providers if p.api_key]


def text_providers() -> list[Provider]:
    """纯文字：DeepSeek，失败时退到 ChatGPT。"""
    s = get_settings()
    providers = [
        Provider("deepseek", s.deepseek_base_url, s.deepseek_api_key, s.deepseek_model, True),
        Provider("openai", s.openai_base_url, s.openai_api_key, "gpt-4.1-mini", True),
    ]
    return [p for p in providers if p.api_key]


def image_part(data: bytes, content_type: str = "image/jpeg") -> dict:
    b64 = base64.b64encode(data).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}}


def parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise AIError("模型没有返回 JSON")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise AIError(f"JSON 解析失败：{e}") from e


def chat_json(provider: Provider, system: str, user_content: list[dict] | str, timeout: float | None = None) -> dict:
    body = {
        "model": provider.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        "temperature": 0.1,
    }
    if provider.json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post(
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=body,
            timeout=timeout or get_settings().ai_timeout_seconds,
        )
    except httpx.HTTPError as e:
        raise AIError(f"{provider.name} 请求失败：{e}") from e
    if resp.status_code != 200:
        raise AIError(f"{provider.name} 返回 {resp.status_code}: {resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise AIError(f"{provider.name} 返回格式不对") from e
    return parse_json(content)
