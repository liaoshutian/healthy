import csv
import io
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Session, User, current_user, get_db, tier_of
from app.models import BodyRecord, MealLog, Upload
from app.services import clock, daily, membership, quota
from app.services.storage import get_storage

router = APIRouter(prefix="/api/me", tags=["me"])


def avatar_url(db: Session, user: User) -> str | None:
    """头像存的是 upload:<id>，每次返回时现签一个临时链接，避免链接过期。"""
    v = user.avatar_url
    if v and v.startswith("upload:"):
        from app.api.uploads import file_url

        up = db.get(Upload, int(v[7:]))
        return file_url(up) if up and up.user_id == user.id else None
    return v


def user_public(db: Session, user: User) -> dict:
    tier, end_at = membership.effective_tier(db, user)
    today = clock.today()
    return {
        "id": user.id,
        "member_id": f"QN{user.id:06d}",
        "nickname": user.nickname,
        "avatar_url": avatar_url(db, user),
        "gender": user.gender,
        "birthday": user.birthday,
        "height_cm": user.height_cm,
        "onboarded": user.onboarded,
        "health_consent": user.health_consent_at is not None,
        "medical_consent": user.medical_consent_at is not None,
        "tier": tier,
        "tier_end_at": end_at,
        "quotas": [quota.usage(f, user.id, tier, today) for f in quota.LIMITS],
    }


@router.get("")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_public(db, user)


class ProfileIn(BaseModel):
    nickname: str | None = Field(default=None, max_length=32)
    avatar_upload_id: int | None = None
    gender: str | None = Field(default=None, pattern="^(male|female)$")
    birthday: date | None = None
    height_cm: float | None = Field(default=None, ge=80, le=250)
    onboarded: bool | None = None


@router.patch("")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    upload_id = data.pop("avatar_upload_id", None)
    if upload_id is not None:
        up = db.get(Upload, upload_id)
        if not up or up.user_id != user.id:
            raise HTTPException(404, "没找到这张图片")
        user.avatar_url = f"upload:{up.id}"
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    return user_public(db, user)


class ConsentIn(BaseModel):
    kind: str = Field(pattern="^(health|medical)$")


@router.post("/consent")
def consent(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.kind == "health":
        user.health_consent_at = clock.now()
    else:
        user.medical_consent_at = clock.now()
    db.commit()
    return user_public(db, user)


@router.get("/badges")
def my_badges(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return daily.badges(db, user)


@router.get("/export")
def export(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """导出饮食和身体数据（CSV，Excel 可直接打开）。Pro 及以上。"""
    if tier_of(db, user) == "free":
        raise HTTPException(402, "数据导出是 Pro 权益")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(["日期", "餐次", "食物", "份量", "克", "千卡", "碳水g", "蛋白质g", "脂肪g"])
        for m in db.scalars(select(MealLog).where(MealLog.user_id == user.id).order_by(MealLog.date)):
            for i in m.items:
                w.writerow([m.date, daily.MEAL_LABELS[m.meal_type], i.name, f"{i.unit_count:g}{i.unit_name}", i.grams, i.kcal, i.carb, i.protein, i.fat])
        z.writestr("饮食记录.csv", "﻿" + s.getvalue())
        s = io.StringIO()
        w = csv.writer(s)
        cols = ["measured_at", "source", "weight_kg", "bmi", "body_fat_pct", "body_fat_kg", "skeletal_muscle_kg", "visceral_fat_level", "bmr_kcal"]
        w.writerow(["测量时间", "来源", "体重kg", "BMI", "体脂率%", "体脂肪kg", "骨骼肌kg", "内脏脂肪等级", "基础代谢kcal"])
        for b in db.scalars(select(BodyRecord).where(BodyRecord.user_id == user.id).order_by(BodyRecord.measured_at)):
            w.writerow([getattr(b, c) for c in cols])
        z.writestr("身体数据.csv", "﻿" + s.getvalue())
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=qingning-export.zip"})


@router.delete("")
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """注销账号：删掉所有记录和图片。"""
    storage = get_storage()
    for up in db.scalars(select(Upload).where(Upload.user_id == user.id)):
        storage.delete(up.key)
    db.delete(user)
    db.commit()
    return {"ok": True}
