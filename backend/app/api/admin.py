"""管理后台接口（请求头 X-Admin-Token）。页面在 /admin。"""
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import Session, get_db
from app.models import AIJob, Food, MembershipLog, RedeemCode, Subscription, User
from app.security import require_admin
from app.services import clock, membership

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CodesIn(BaseModel):
    tier: str = Field(pattern="^(pro|max)$")
    days: int = Field(ge=1, le=3650)
    count: int = Field(ge=1, le=500)
    batch: str | None = Field(default=None, max_length=64)
    redeem_before: date | None = None


@router.post("/codes")
def generate(body: CodesIn, db: Session = Depends(get_db)):
    codes = membership.generate_codes(db, body.tier, body.days, body.count, body.batch, body.redeem_before)
    return {"codes": codes}


@router.get("/codes")
def list_codes(batch: str | None = None, used: bool | None = None, limit: int = 200, db: Session = Depends(get_db)):
    q = select(RedeemCode)
    if batch:
        q = q.where(RedeemCode.batch == batch)
    if used is True:
        q = q.where(RedeemCode.used_by.is_not(None))
    elif used is False:
        q = q.where(RedeemCode.used_by.is_(None))
    rows = db.scalars(q.order_by(RedeemCode.id.desc()).limit(min(limit, 1000)))
    return [{"code": c.code, "tier": c.tier, "days": c.days, "batch": c.batch, "redeem_before": c.redeem_before,
             "used_by": c.used_by, "used_at": c.used_at, "revoked": c.revoked, "created_at": c.created_at} for c in rows]


@router.post("/codes/{code}/revoke")
def revoke_code(code: str, db: Session = Depends(get_db)):
    c = db.scalar(select(RedeemCode).where(RedeemCode.code == membership.normalize_code(code)))
    if not c:
        raise HTTPException(404)
    c.revoked = True
    db.commit()
    return {"ok": True}


def _user_row(db: Session, u: User) -> dict:
    tier, end = membership.effective_tier(db, u)
    return {"id": u.id, "member_id": f"QN{u.id:06d}", "nickname": u.nickname, "tier": tier, "end_at": end, "created_at": u.created_at}


def _parse_member_id(q: str) -> int | None:
    q = q.strip().upper()
    if q.startswith("QN"):
        q = q[2:]
    return int(q) if q.isdigit() else None


@router.get("/users")
def users(q: str = "", db: Session = Depends(get_db)):
    stmt = select(User)
    if q:
        uid = _parse_member_id(q)
        stmt = stmt.where(or_(User.id == uid, User.nickname.contains(q)) if uid else User.nickname.contains(q))
    return [_user_row(db, u) for u in db.scalars(stmt.order_by(User.id.desc()).limit(50))]


class GrantIn(BaseModel):
    tier: str = Field(pattern="^(pro|max)$")
    days: int = Field(ge=1, le=3650)
    note: str | None = Field(default=None, max_length=200)


@router.post("/users/{uid}/grant")
def grant(uid: int, body: GrantIn, db: Session = Depends(get_db)):
    """按会员 ID 手动开通/延期。"""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "没有这个用户")
    membership.grant(db, u, body.tier, body.days, "admin", note=body.note)
    db.commit()
    return _user_row(db, u)


@router.post("/users/{uid}/revoke")
def revoke(uid: int, db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    membership.revoke(db, u)
    db.commit()
    return _user_row(db, u)


@router.get("/expiring")
def expiring(days: int = 7, fmt: str = "json", db: Session = Depends(get_db)):
    """N 天内到期名单，方便在星球提醒续费。"""
    now = clock.now()
    rows = db.execute(select(Subscription, User).join(User, User.id == Subscription.user_id).where(
        Subscription.end_at > now, Subscription.end_at <= now + timedelta(days=days)).order_by(Subscription.end_at))
    data = [{"member_id": f"QN{u.id:06d}", "nickname": u.nickname, "tier": s.tier, "end_at": s.end_at} for s, u in rows]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["会员ID", "昵称", "档位", "到期时间"])
        for d in data:
            w.writerow([d["member_id"], d["nickname"] or "", d["tier"], d["end_at"]])
        return Response("﻿" + buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=expiring.csv"})
    return data


@router.get("/logs")
def logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(MembershipLog).order_by(MembershipLog.id.desc()).limit(min(limit, 500)))
    return [{"user_id": l.user_id, "member_id": f"QN{l.user_id:06d}", "source": l.source, "tier": l.tier, "days": l.days,
             "code": l.code, "end_at": l.end_at, "note": l.note, "created_at": l.created_at} for l in rows]


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    today_start = clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ai = db.execute(select(AIJob.kind, AIJob.status, func.count()).where(AIJob.created_at >= today_start).group_by(AIJob.kind, AIJob.status))
    return {"users": db.scalar(select(func.count(User.id))),
            "active_subscriptions": db.scalar(select(func.count(Subscription.id)).where(Subscription.end_at > clock.now())),
            "ai_today": [{"kind": k, "status": s, "count": c} for k, s, c in ai],
            "pending_foods": db.scalar(select(func.count(Food.id)).where(Food.verified.is_(False)))}


@router.get("/foods/pending")
def pending_foods(db: Session = Depends(get_db)):
    rows = db.scalars(select(Food).where(Food.verified.is_(False)).order_by(Food.id.desc()).limit(200))
    return [{"id": f.id, "name": f.name, "category": f.category, "kcal": round(f.kcal), "carb": round(f.carb, 1),
             "protein": round(f.protein, 1), "fat": round(f.fat, 1), "unit_name": f.unit_name, "unit_grams": f.unit_grams} for f in rows]


class FoodReviewIn(BaseModel):
    approve: bool
    category: str | None = None
    kcal: float | None = None
    carb: float | None = None
    protein: float | None = None
    fat: float | None = None
    unit_name: str | None = None
    unit_grams: float | None = None
    tags: list[str] | None = None


@router.post("/foods/{fid}/review")
def review_food(fid: int, body: FoodReviewIn, db: Session = Depends(get_db)):
    f = db.get(Food, fid)
    if not f:
        raise HTTPException(404)
    if not body.approve:
        db.delete(f)
    else:
        for k, v in body.model_dump(exclude={"approve"}, exclude_none=True).items():
            setattr(f, k, v)
        f.verified = True
    db.commit()
    return {"ok": True}
