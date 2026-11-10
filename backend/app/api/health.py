"""身体不适、用药、就诊病历（方案 4.8）。只做记录和整理，不做病情判断和用药建议。"""
from datetime import date, datetime, timedelta

DateT = date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Session, User, get_db, own, own_upload, require_medical_consent, tier_of
from app.api.uploads import file_url
from app.data.meta import part_label
from app.models import MedicalRecord, MedicationLog, SymptomLog, SymptomUpdate, Upload
from app.services import clock, quota
from app.services.ai.service import AllProvidersFailed, read_medicine
from app.services.storage import get_storage

router = APIRouter(prefix="/api", tags=["health"])
DISCLAIMER = "这里只做记录和整理，不替代医生诊断。"


# ---------- 不适 ----------

class PartIn(BaseModel):
    code: str = Field(max_length=48)
    note: str | None = Field(default=None, max_length=50)
    x: float | None = None  # 局部图上点的位置（0-1）
    y: float | None = None


class SymptomIn(BaseModel):
    parts: list[PartIn] = Field(min_length=1, max_length=10)
    symptoms: list[str] = Field(default_factory=list, max_length=10)
    severity: int = Field(ge=1, le=10)
    started_at: datetime | None = None
    temperature: float | None = Field(default=None, ge=34, le=43)
    note: str | None = Field(default=None, max_length=500)


def _parts(parts: list[PartIn]) -> list[dict]:
    out = []
    for p in parts:
        label = part_label(p.code)
        if not label:
            raise HTTPException(400, f"不认识的部位：{p.code}")
        out.append({"code": p.code, "label": label, "note": p.note, "x": p.x, "y": p.y})
    return out


def symptom_public(db: Session, s: SymptomLog, full: bool = False) -> dict:
    start = s.started_at.astimezone(clock.TZ).date() if s.started_at.tzinfo else s.started_at.date()
    end = (s.healed_at.astimezone(clock.TZ).date() if s.healed_at and s.healed_at.tzinfo else s.healed_at.date()) if s.healed_at else clock.today()
    out = {"id": s.id, "parts": s.parts, "symptoms": s.symptoms, "severity": s.severity, "started_at": s.started_at,
           "temperature": s.temperature, "status": s.status, "healed_at": s.healed_at, "note": s.note,
           "days": (end - start).days + 1}
    if full:
        out["updates"] = [{"date": u.date, "severity": u.severity, "temperature": u.temperature, "note": u.note} for u in s.updates]
        out["medications"] = [med_public(db, m) for m in db.scalars(select(MedicationLog).where(MedicationLog.symptom_id == s.id))]
        out["records"] = [record_public(db, r) for r in db.scalars(select(MedicalRecord).where(MedicalRecord.symptom_id == s.id))]
        out["disclaimer"] = DISCLAIMER
    return out


@router.get("/symptoms")
def list_symptoms(status: str | None = None, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    q = select(SymptomLog).where(SymptomLog.user_id == user.id)
    if status:
        q = q.where(SymptomLog.status == status)
    return [symptom_public(db, s) for s in db.scalars(q.order_by(SymptomLog.started_at.desc()).limit(100))]


@router.get("/symptoms/last-at")
def last_at(code: str, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    """“上次也是这里”：同一部位（或它的上级/下级）上一次不舒服是什么时候。"""
    for s in db.scalars(select(SymptomLog).where(SymptomLog.user_id == user.id).order_by(SymptomLog.started_at.desc())):
        for p in s.parts or []:
            if p["code"] == code or p["code"].startswith(code + ".") or code.startswith(p["code"] + "."):
                return {"symptom_id": s.id, "started_at": s.started_at, "label": p["label"], "symptoms": s.symptoms,
                        "text": f"上次也是这里：{s.started_at.astimezone(clock.TZ):%Y年%m月%d日}，{'、'.join(s.symptoms) or '不舒服'}"}
    return None


@router.post("/symptoms")
def create_symptom(body: SymptomIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    s = SymptomLog(user_id=user.id, parts=_parts(body.parts), symptoms=body.symptoms, severity=body.severity,
                   started_at=body.started_at or clock.now(), temperature=body.temperature, note=body.note)
    db.add(s)
    db.flush()
    db.add(SymptomUpdate(symptom_id=s.id, date=clock.today(), severity=body.severity, temperature=body.temperature, note=body.note))
    db.commit()
    return symptom_public(db, s, full=True)


@router.get("/symptoms/{sid}")
def get_symptom(sid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    return symptom_public(db, own(db, SymptomLog, sid, user), full=True)


@router.put("/symptoms/{sid}")
def update_symptom(sid: int, body: SymptomIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    s = own(db, SymptomLog, sid, user)
    s.parts, s.symptoms, s.severity, s.temperature, s.note = _parts(body.parts), body.symptoms, body.severity, body.temperature, body.note
    if body.started_at:
        s.started_at = body.started_at
    db.commit()
    return symptom_public(db, s, full=True)


@router.delete("/symptoms/{sid}")
def delete_symptom(sid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    db.delete(own(db, SymptomLog, sid, user))
    db.commit()
    return {"ok": True}


class FollowIn(BaseModel):
    severity: int = Field(ge=0, le=10)
    temperature: float | None = Field(default=None, ge=34, le=43)
    note: str | None = Field(default=None, max_length=200)
    date: DateT | None = None


@router.post("/symptoms/{sid}/updates")
def follow_up(sid: int, body: FollowIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    """每日跟进：“今天好些了吗？”同一天再记会覆盖。"""
    s = own(db, SymptomLog, sid, user)
    d = body.date or clock.today()
    u = next((x for x in s.updates if x.date == d), None)
    if not u:
        u = SymptomUpdate(symptom_id=s.id, date=d, severity=body.severity)
        s.updates.append(u)
    u.severity, u.temperature, u.note = body.severity, body.temperature, body.note
    s.severity = body.severity
    db.commit()
    return symptom_public(db, s, full=True)


@router.post("/symptoms/{sid}/heal")
def heal(sid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    s = own(db, SymptomLog, sid, user)
    s.status, s.healed_at = "healed", clock.now()
    db.commit()
    out = symptom_public(db, s, full=True)
    out["cheer"] = f"好起来啦！这次一共 {out['days']} 天，照顾好自己"
    return out


@router.get("/symptoms/{sid}/summary")
def summary(sid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    """给医生看的病情摘要（结构化文字，前端画成图片）。"""
    s = own(db, SymptomLog, sid, user)
    p = symptom_public(db, s, full=True)
    lines = [
        f"不舒服的地方：{'、'.join(x['label'] for x in s.parts)}",
        f"症状：{'、'.join(s.symptoms) or '未填写'}",
        f"开始时间：{s.started_at.astimezone(clock.TZ):%Y-%m-%d %H:%M}（共 {p['days']} 天）",
    ]
    if p["updates"]:
        lines.append("程度变化：" + "，".join(f"{u['date']:%m-%d} {u['severity']}分" + (f" {u['temperature']}℃" if u["temperature"] else "") for u in p["updates"]))
    for m in p["medications"]:
        lines.append(f"用药：{m['name']} {m['spec'] or ''} 每次{m['dose'] or '?'} 每日{m['times_per_day'] or '?'}次，自{m['start_date']}起")
    for r in p["records"]:
        lines.append(f"就诊：{r['visit_date']} {r['hospital'] or ''}{r['department'] or ''} 诊断：{r['diagnosis'] or '未填写'}")
    return {"title": "病情摘要", "lines": lines, "disclaimer": DISCLAIMER, "generated_at": clock.now()}


# ---------- 用药 ----------

class MedIn(BaseModel):
    symptom_id: int | None = None
    name: str = Field(min_length=1, max_length=64)
    spec: str | None = Field(default=None, max_length=64)
    dose: str | None = Field(default=None, max_length=32)
    times_per_day: int | None = Field(default=None, ge=1, le=12)
    course_days: int | None = Field(default=None, ge=1, le=365)
    start_date: date | None = None
    remind: bool = False
    photo_upload_id: int | None = None
    note: str | None = Field(default=None, max_length=200)


def med_public(db: Session, m: MedicationLog) -> dict:
    end = m.start_date + timedelta(days=m.course_days - 1) if m.course_days else None
    return {"id": m.id, "symptom_id": m.symptom_id, "name": m.name, "spec": m.spec, "dose": m.dose,
            "times_per_day": m.times_per_day, "course_days": m.course_days, "start_date": m.start_date, "end_date": end,
            "active": end is None or end >= clock.today(), "remind": m.remind, "reminder_credits": m.reminder_credits,
            "note": m.note, "photo_upload_id": m.photo_upload_id, "photo_url": file_url(db.get(Upload, m.photo_upload_id)) if m.photo_upload_id else None}


@router.post("/medications/recognize")
def recognize_med(body: dict, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    """拍药盒：AI 只读药名和规格，用户确认后保存。"""
    up = own_upload(db, int(body.get("upload_id", 0)), user)
    tier, today = tier_of(db, user), clock.today()
    if not quota.try_consume("medicine", user.id, tier, today):
        return {"fallback": "manual", "reason": "quota", "message": "今天的识别次数用完了，手动填一下吧"}
    try:
        data, _ = read_medicine(db, user.id, get_storage().get(up.key), up.content_type)
    except AllProvidersFailed:
        quota.refund("medicine", user.id, today)
        return {"fallback": "manual", "reason": "ai_failed", "message": "没读出来，手动填一下吧"}
    if not data["is_medicine"]:
        quota.refund("medicine", user.id, today)
        return {"fallback": "manual", "reason": "not_medicine", "message": "这张好像不是药盒"}
    return {**data, "photo_upload_id": up.id}


@router.get("/medications")
def list_meds(user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    rows = db.scalars(select(MedicationLog).where(MedicationLog.user_id == user.id).order_by(MedicationLog.start_date.desc()).limit(100))
    return [med_public(db, m) for m in rows]


def _check_symptom(db, user, sid):
    if sid is not None:
        own(db, SymptomLog, sid, user)


@router.post("/medications")
def create_med(body: MedIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    _check_symptom(db, user, body.symptom_id)
    own_upload(db, body.photo_upload_id, user)
    data = body.model_dump()
    data["start_date"] = data["start_date"] or clock.today()
    m = MedicationLog(user_id=user.id, **data)
    db.add(m)
    db.commit()
    return med_public(db, m)


@router.put("/medications/{mid}")
def update_med(mid: int, body: MedIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    m = own(db, MedicationLog, mid, user)
    _check_symptom(db, user, body.symptom_id)
    own_upload(db, body.photo_upload_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    return med_public(db, m)


@router.post("/medications/{mid}/subscribed")
def med_subscribed(mid: int, body: dict, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    m = own(db, MedicationLog, mid, user)
    m.reminder_credits = min(30, m.reminder_credits + max(0, min(10, int(body.get("accepted", 1)))))
    db.commit()
    return med_public(db, m)


@router.delete("/medications/{mid}")
def delete_med(mid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    db.delete(own(db, MedicationLog, mid, user))
    db.commit()
    return {"ok": True}


# ---------- 就诊与病历 ----------

class RecordIn(BaseModel):
    symptom_id: int | None = None
    visit_date: date | None = None
    hospital: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=32)
    diagnosis: str | None = Field(default=None, max_length=2000)
    image_upload_ids: list[int] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=500)


def record_public(db: Session, r: MedicalRecord) -> dict:
    return {"id": r.id, "symptom_id": r.symptom_id, "visit_date": r.visit_date, "hospital": r.hospital,
            "department": r.department, "diagnosis": r.diagnosis, "note": r.note, "ocr_text": r.ocr_text,
            "images": [{"id": uid, "url": file_url(db.get(Upload, uid))} for uid in r.image_upload_ids or [] if db.get(Upload, uid)]}


@router.get("/medical-records")
def list_records(user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    rows = db.scalars(select(MedicalRecord).where(MedicalRecord.user_id == user.id).order_by(MedicalRecord.visit_date.desc()).limit(100))
    return [record_public(db, r) for r in rows]


@router.post("/medical-records")
def create_record(body: RecordIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    _check_symptom(db, user, body.symptom_id)
    for uid in body.image_upload_ids:
        own_upload(db, uid, user)
    data = body.model_dump()
    data["visit_date"] = data["visit_date"] or clock.today()
    r = MedicalRecord(user_id=user.id, **data)
    db.add(r)
    db.commit()
    return record_public(db, r)


@router.put("/medical-records/{rid}")
def update_record(rid: int, body: RecordIn, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    r = own(db, MedicalRecord, rid, user)
    _check_symptom(db, user, body.symptom_id)
    for uid in body.image_upload_ids:
        own_upload(db, uid, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    return record_public(db, r)


@router.delete("/medical-records/{rid}")
def delete_record(rid: int, user: User = Depends(require_medical_consent), db: Session = Depends(get_db)):
    r = own(db, MedicalRecord, rid, user)
    storage = get_storage()
    for uid in r.image_upload_ids or []:
        up = db.get(Upload, uid)
        if up and up.user_id == user.id:
            storage.delete(up.key)
            db.delete(up)
    db.delete(r)
    db.commit()
    return {"ok": True}
