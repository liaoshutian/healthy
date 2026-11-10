from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Session, User, current_user, get_db, own, own_upload, tier_of
from app.api.uploads import file_url
from app.models import BodyRecord, Upload
from app.services import clock, quota
from app.services.ai.prompts import INBODY_FIELDS
from app.services.ai.service import AllProvidersFailed, interpret_body, read_inbody
from app.services.storage import get_storage

router = APIRouter(prefix="/api/body", tags=["body"])

NUM_FIELDS = [k for k in INBODY_FIELDS if k not in ("measured_at", "height_cm")]
LOW_CONFIDENCE = 0.7


def ranges(user: User) -> dict:
    """偏低/标准/偏高的分界。BMI 用中国成人标准；体脂率按性别。"""
    fat = (10, 20) if user.gender == "male" else (18, 28) if user.gender == "female" else (14, 25)
    return {"bmi": (18.5, 24), "body_fat_pct": fat, "visceral_fat_level": (1, 9)}


def level(value: float | None, rng: tuple[float, float] | None) -> str | None:
    if value is None or rng is None:
        return None
    if value < rng[0]:
        return "low"
    if value > rng[1]:
        return "high"
    return "normal"


def record_public(db: Session, user: User, r: BodyRecord, prev: BodyRecord | None = None) -> dict:
    rg = ranges(user)
    fields = {}
    for k in NUM_FIELDS:
        v = getattr(r, k)
        pv = getattr(prev, k) if prev else None
        fields[k] = {"value": v, "level": level(v, rg.get(k)), "range": rg.get(k),
                     "delta": round(v - pv, 2) if v is not None and pv is not None else None,
                     "confidence": (r.confidence or {}).get(k)}
    return {"id": r.id, "measured_at": r.measured_at, "source": r.source, "fields": fields, "segments": r.segments,
            "note": r.note, "image_url": file_url(db.get(Upload, r.image_upload_id)) if r.image_upload_id else None}


def _require_health_consent(user: User):
    if not user.health_consent_at:
        raise HTTPException(428, "记录体成分前需要先同意《健康数据授权》")


class RecognizeIn(BaseModel):
    upload_id: int


@router.post("/recognize")
def recognize(body: RecognizeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """拍 InBody → 草稿。低置信度字段 confidence < 0.7，前端标黄。失败返回 fallback=manual 并保留已读字段。"""
    _require_health_consent(user)
    up = own_upload(db, body.upload_id, user)
    tier, today = tier_of(db, user), clock.today()
    if not quota.try_consume("inbody", user.id, tier, today):
        return {"fallback": "manual", "reason": "quota", "message": "这个月的报告识别次数用完了，可以手动填一下"}
    try:
        data, provider = read_inbody(db, user.id, get_storage().get(up.key), up.content_type)
    except AllProvidersFailed:
        quota.refund("inbody", user.id, today)
        return {"fallback": "manual", "reason": "ai_failed", "message": "没读出来，平放、避开反光再拍一次，或者手动填"}
    if not data["is_report"]:
        quota.refund("inbody", user.id, today)
        return {"fallback": "manual", "reason": "not_report", "message": "这张好像不是体成分报告"}
    f = data["fields"]
    if f.get("height_cm") and not user.height_cm:
        user.height_cm = f["height_cm"]
        db.commit()
    low = [k for k, c in data["confidence"].items() if f.get(k) is not None and c < LOW_CONFIDENCE]
    return {"provider": provider, "model": data.get("model"), "fields": f, "confidence": data["confidence"],
            "low_confidence": low, "segments": data.get("segments"), "image_upload_id": up.id, "image_url": file_url(up)}


class BodyIn(BaseModel):
    measured_at: datetime | None = None
    source: str = Field(default="manual", pattern="^(inbody|manual|weight)$")
    weight_kg: float | None = Field(default=None, gt=20, lt=300)
    bmi: float | None = Field(default=None, gt=8, lt=80)
    body_fat_pct: float | None = Field(default=None, ge=1, le=75)
    body_fat_kg: float | None = Field(default=None, ge=0, le=200)
    fat_free_mass_kg: float | None = Field(default=None, ge=0, le=200)
    skeletal_muscle_kg: float | None = Field(default=None, ge=0, le=100)
    visceral_fat_level: float | None = Field(default=None, ge=0, le=30)
    bmr_kcal: float | None = Field(default=None, ge=500, le=5000)
    body_water_kg: float | None = Field(default=None, ge=0, le=150)
    protein_kg: float | None = Field(default=None, ge=0, le=50)
    mineral_kg: float | None = Field(default=None, ge=0, le=20)
    inbody_score: float | None = Field(default=None, ge=0, le=120)
    segments: dict | None = None
    confidence: dict | None = None
    image_upload_id: int | None = None
    note: str | None = Field(default=None, max_length=500)
    confirm_big_change: bool = False


@router.post("")
def create(body: BodyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_health_consent(user)
    own_upload(db, body.image_upload_id, user)
    prev = latest(db, user)
    if prev and prev.weight_kg and body.weight_kg and abs(prev.weight_kg - body.weight_kg) >= 10 and not body.confirm_big_change:
        raise HTTPException(409, f"和上次差了 {abs(prev.weight_kg - body.weight_kg):.1f} kg，确认没填错吗？")
    data = body.model_dump(exclude={"confirm_big_change"})
    data["measured_at"] = data["measured_at"] or clock.now()
    if data["bmi"] is None and data["weight_kg"] and user.height_cm:
        data["bmi"] = round(data["weight_kg"] / (user.height_cm / 100) ** 2, 1)
    r = BodyRecord(user_id=user.id, **data)
    db.add(r)
    db.commit()
    celebrate = bool(prev and prev.body_fat_pct and r.body_fat_pct and r.body_fat_pct < prev.body_fat_pct) or bool(
        prev and prev.skeletal_muscle_kg and r.skeletal_muscle_kg and r.skeletal_muscle_kg > prev.skeletal_muscle_kg)
    return {**record_public(db, user, r, prev), "celebrate": celebrate}


def latest(db: Session, user: User, before: datetime | None = None) -> BodyRecord | None:
    q = select(BodyRecord).where(BodyRecord.user_id == user.id)
    if before:
        q = q.where(BodyRecord.measured_at < before)
    return db.scalar(q.order_by(BodyRecord.measured_at.desc()).limit(1))


@router.get("")
def list_records(limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(BodyRecord).where(BodyRecord.user_id == user.id).order_by(BodyRecord.measured_at.desc()).limit(min(limit, 200)))
    return [{"id": r.id, "measured_at": r.measured_at, "source": r.source, "weight_kg": r.weight_kg,
             "body_fat_pct": r.body_fat_pct, "skeletal_muscle_kg": r.skeletal_muscle_kg} for r in rows]


@router.get("/{rid}")
def detail(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = own(db, BodyRecord, rid, user)
    return record_public(db, user, r, latest(db, user, before=r.measured_at))


@router.post("/{rid}/interpret")
def interpret(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """AI 文字解读，Pro 及以上。"""
    if tier_of(db, user) == "free":
        raise HTTPException(402, "AI 解读是 Pro 权益")
    r = own(db, BodyRecord, rid, user)
    prev = latest(db, user, before=r.measured_at)
    pick = lambda x: {k: getattr(x, k) for k in NUM_FIELDS if getattr(x, k) is not None}  # noqa: E731
    result = interpret_body(db, user.id, {"性别": user.gender, **pick(r)}, pick(prev) if prev else None)
    if not result:
        raise HTTPException(503, "解读暂时生成不了，等会儿再试")
    return {**result, "ai_generated": True}


@router.delete("/{rid}")
def delete(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(own(db, BodyRecord, rid, user))
    db.commit()
    return {"ok": True}
