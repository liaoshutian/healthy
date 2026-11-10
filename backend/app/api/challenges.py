from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Session, User, current_user, get_db, own
from app.models import Challenge, MealLog
from app.services import clock, daily, plans
from app.services.daily import item_dict

router = APIRouter(prefix="/api", tags=["challenges"])


@router.get("/plans")
def list_plans():
    return [plans.plan_public(p) for p in plans.PLANS.values()]


@router.get("/plans/recommend")
def recommend(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """用过去 14 天的饭推荐最像的挑战卡。"""
    since = clock.today() - timedelta(days=14)
    meals = db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.date >= since))
    return plans.recommend([[item_dict(i) for i in m.items] for m in meals])


@router.get("/challenges")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = clock.today()
    _finish_expired(db, user)
    rows = db.scalars(select(Challenge).where(Challenge.user_id == user.id).order_by(Challenge.id.desc()).limit(20))
    return [daily.challenge_public(c, today) for c in rows]


def _finish_expired(db: Session, user: User) -> None:
    today = clock.today()
    for c in db.scalars(select(Challenge).where(Challenge.user_id == user.id, Challenge.status == "active")):
        if (today - c.start_date).days >= c.days:
            c.status, c.ended_at = "done", clock.now()
    db.commit()


class StartIn(BaseModel):
    plan_code: str
    trial: bool = False
    days: int | None = Field(default=None, ge=3, le=90)


@router.post("/challenges")
def start(body: StartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """开一张挑战卡。同时只有一张进行中，换卡时旧卡自动停下，不算失败。"""
    plan = plans.PLANS.get(body.plan_code)
    if not plan:
        raise HTTPException(404, "没有这张卡")
    for c in db.scalars(select(Challenge).where(Challenge.user_id == user.id, Challenge.status.in_(["active", "paused"]))):
        c.status, c.ended_at = "stopped", clock.now()
    days = 3 if body.trial else (body.days or plan.suggested_days)
    c = Challenge(user_id=user.id, plan_code=plan.code, days=days, start_date=clock.today(), status="active")
    db.add(c)
    db.commit()
    return daily.challenge_public(c, clock.today())


class ActionIn(BaseModel):
    action: str = Field(pattern="^(pause|resume|stop)$")


@router.post("/challenges/{cid}/action")
def act(cid: int, body: ActionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = own(db, Challenge, cid, user)
    if body.action == "pause" and c.status == "active":
        c.status = "paused"
    elif body.action == "resume" and c.status == "paused":
        for other in db.scalars(select(Challenge).where(Challenge.user_id == user.id, Challenge.status == "active")):
            other.status = "stopped"
        c.status = "active"
    elif body.action == "stop":
        c.status, c.ended_at = "stopped", clock.now()
    db.commit()
    return daily.challenge_public(c, clock.today())
