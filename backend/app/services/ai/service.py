"""AI 任务编排：按顺序尝试多家模型，主模型超时、报错或校验不通过就切换下一家。每次调用记一条 AIJob。"""
import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models import AIJob
from app.services.ai import prompts
from app.services.ai.client import AIError, Provider, chat_json, image_part, text_providers, vision_providers

log = logging.getLogger(__name__)


class AllProvidersFailed(Exception):
    pass


def _run(
    db: Session,
    user_id: int | None,
    kind: str,
    providers: list[Provider],
    system: str,
    content,
    validate: Callable[[dict], dict],
) -> tuple[dict, str]:
    if not providers:
        raise AllProvidersFailed("没有配置可用的大模型")
    errors = []
    for i, p in enumerate(providers):
        t0 = time.monotonic()
        try:
            data = validate(chat_json(p, system, content))
        except (AIError, ValueError, KeyError, TypeError) as e:
            errors.append(f"{p.name}: {e}")
            db.add(AIJob(user_id=user_id, kind=kind, status="failed", provider=p.name, model=p.model,
                         latency_ms=int((time.monotonic() - t0) * 1000), error=str(e)[:1000]))
            db.commit()
            log.warning("AI %s via %s failed: %s", kind, p.name, e)
            continue
        db.add(AIJob(user_id=user_id, kind=kind, status="ok" if i == 0 else "fallback_ok", provider=p.name,
                     model=p.model, latency_ms=int((time.monotonic() - t0) * 1000)))
        db.commit()
        return data, p.name
    raise AllProvidersFailed("; ".join(errors))


# ---------- 校验 ----------

def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace(",", "").strip())


def validate_inbody(data: dict) -> dict:
    """生理关系交叉检查，不满足的字段降置信度（方案 5.1）。核心字段全空视为识别失败，触发切换模型。"""
    if not data.get("is_report", True):
        return {"is_report": False, "fields": {}, "confidence": {}, "segments": None}
    raw = data.get("fields") or {}
    values, conf = {}, {}
    for key in prompts.INBODY_FIELDS:
        f = raw.get(key)
        if isinstance(f, dict):
            v, c = f.get("value"), f.get("confidence", 0.8)
        else:
            v, c = f, 0.8
        if key == "measured_at":
            values[key] = v or None
        else:
            try:
                values[key] = _num(v)
            except ValueError:
                values[key] = None
        conf[key] = float(c or 0) if values[key] is not None else 0.0

    w, h = values.get("weight_kg"), values.get("height_cm")
    if not w:
        raise ValueError("没读到体重，换一个模型再试")
    if values.get("bmi") and h:
        if abs(values["bmi"] - w / (h / 100) ** 2) > 1.0:
            conf["bmi"] = min(conf["bmi"], 0.4)
            conf["weight_kg"] = min(conf["weight_kg"], 0.6)
    if values.get("body_fat_kg") and values.get("fat_free_mass_kg"):
        if abs(values["body_fat_kg"] + values["fat_free_mass_kg"] - w) > 1.0:
            conf["body_fat_kg"] = min(conf["body_fat_kg"], 0.4)
            conf["fat_free_mass_kg"] = min(conf["fat_free_mass_kg"], 0.4)
    if values.get("body_fat_kg") and values.get("body_fat_pct"):
        if abs(values["body_fat_kg"] / w * 100 - values["body_fat_pct"]) > 1.5:
            conf["body_fat_pct"] = min(conf["body_fat_pct"], 0.4)
    low = sum(1 for k in ("bmi", "body_fat_kg", "body_fat_pct") if values.get(k) and conf[k] < 0.5)
    if low >= 2:
        raise ValueError("多项指标对不上，换一个模型再试")
    return {"is_report": True, "model": data.get("model"), "fields": values, "confidence": conf, "segments": data.get("segments")}


def validate_food(data: dict) -> dict:
    if not data.get("is_food", True):
        return {"is_food": False, "items": []}
    items = []
    for it in data.get("items") or []:
        name = str(it.get("name") or "").strip()
        grams = _num(it.get("grams"))
        if not name or not grams or grams <= 0 or grams > 3000:
            continue
        items.append({
            "name": name,
            "candidates": [str(c) for c in (it.get("candidates") or [])][:2],
            "cooking": it.get("cooking"),
            "grams": grams,
            "count": _num(it.get("count")) if it.get("count") not in (None, "") else None,
            "unit": it.get("unit"),
            "x": it.get("x"),
            "y": it.get("y"),
            "category": it.get("category"),
            "per100g": it.get("per100g") if isinstance(it.get("per100g"), dict) else None,
        })
    if not items:
        raise ValueError("没识别出食物条目")
    return {"is_food": True, "items": items}


def validate_medicine(data: dict) -> dict:
    if not data.get("is_medicine", True):
        return {"is_medicine": False}
    if not data.get("name"):
        raise ValueError("没读到药名")
    return {"is_medicine": True, "name": data["name"], "spec": data.get("spec"), "usage": data.get("usage")}


# ---------- 对外接口 ----------

def read_inbody(db: Session, user_id: int, image: bytes, content_type: str) -> tuple[dict, str]:
    content = [{"type": "text", "text": "请读取这张体成分报告。"}, image_part(image, content_type)]
    return _run(db, user_id, "inbody", vision_providers(), prompts.INBODY_SYSTEM, content, validate_inbody)


def recognize_food(db: Session, user_id: int, image: bytes, content_type: str) -> tuple[dict, str]:
    content = [{"type": "text", "text": "请识别这顿饭。"}, image_part(image, content_type)]
    return _run(db, user_id, "food", vision_providers(), prompts.FOOD_SYSTEM, content, validate_food)


def read_medicine(db: Session, user_id: int, image: bytes, content_type: str) -> tuple[dict, str]:
    content = [{"type": "text", "text": "请读出这个药盒上的信息。"}, image_part(image, content_type)]
    return _run(db, user_id, "medicine", vision_providers(), prompts.MEDICINE_SYSTEM, content, validate_medicine)


def parse_meal_text(db: Session, user_id: int, text: str) -> tuple[dict, str]:
    def v(d):
        return validate_food({"is_food": True, "items": d.get("items")})

    return _run(db, user_id, "text", text_providers(), prompts.MEAL_TEXT_SYSTEM, text, v)


def interpret_body(db: Session, user_id: int, current: dict, previous: dict | None) -> dict | None:
    import json

    msg = json.dumps({"本次": current, "上次": previous}, ensure_ascii=False, default=str)

    def v(d):
        if not d.get("summary"):
            raise ValueError("没有 summary")
        return {"summary": d["summary"], "highlights": d.get("highlights", [])[:3], "next_steps": d.get("next_steps", [])[:3]}

    try:
        data, _ = _run(db, user_id, "text", text_providers(), prompts.BODY_INTERPRET_SYSTEM, msg, v)
        return data
    except AllProvidersFailed:
        return None
