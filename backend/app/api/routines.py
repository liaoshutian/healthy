from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import Session, User, current_user, get_db, own, tier_of
from app.api.uploads import file_url
from app.data.meta import ROUTINE_TEMPLATES
from app.models import Routine, RoutineLog, Upload
from app.services import clock
from app.services.routines import average_cycle, status

router = APIRouter(prefix="/api/routines", tags=["routines"])
FREE_LIMIT = 3


def public(r: Routine, today: date) -> dict:
    return {"id": r.id, "name": r.name, "icon": r.icon, "cycle_days": r.cycle_days,
            "remind_days_before": r.remind_days_before, "last_done_date": r.last_done_date,
            "reminder_credits": r.reminder_credits, **status(r, today)}


@router.get("/templates")
def templates():
    return ROUTINE_TEMPLATES


@router.get("")
def list_routines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = clock.today()
    rows = [public(r, today) for r in db.scalars(select(Routine).where(Routine.user_id == user.id, Routine.archived.is_(False)))]
    order = {"overdue": 0, "due": 1, "soon": 2, "ok": 3}
    rows.sort(key=lambda x: (order[x["state"]], x["days_left"]))
    return rows


class RoutineIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    icon: str = Field(default="⭐", max_length=16)
    cycle_days: int = Field(ge=1, le=3650)
    remind_days_before: int = Field(default=1, ge=0, le=60)
    last_done_date: date | None = None


@router.post("")
def create(body: RoutineIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if tier_of(db, user) == "free":
        n = db.scalar(select(func.count(Routine.id)).where(Routine.user_id == user.id, Routine.archived.is_(False)))
        if n >= FREE_LIMIT:
            raise HTTPException(402, f"免费版最多管 {FREE_LIMIT} 件规律小事，Pro 不限")
    r = Routine(user_id=user.id, **body.model_dump())
    db.add(r)
    db.commit()
    return public(r, clock.today())


@router.put("/{rid}")
def update(rid: int, body: RoutineIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = own(db, Routine, rid, user)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return public(r, clock.today())


@router.delete("/{rid}")
def archive(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    own(db, Routine, rid, user).archived = True
    db.commit()
    return {"ok": True}


class DoneIn(BaseModel):
    done_date: date | None = None
    note: str | None = Field(default=None, max_length=200)
    cost: float | None = Field(default=None, ge=0, le=100000)
    photo_upload_ids: list[int] = Field(default_factory=list, max_length=9)


@router.post("/{rid}/done")
def done(rid: int, body: DoneIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """“今天完成了”：重新计时。"""
    r = own(db, Routine, rid, user)
    for uid in body.photo_upload_ids:
        own(db, Upload, uid, user)
    d = body.done_date or clock.today()
    db.add(RoutineLog(routine_id=r.id, user_id=user.id, done_date=d, note=body.note, cost=body.cost, photo_upload_ids=body.photo_upload_ids))
    if not r.last_done_date or d >= r.last_done_date:
        r.last_done_date = d
    r.snooze_until = None
    db.commit()
    return {**public(r, clock.today()), "cheer": f"{r.name}完成啦，下次大约在 {status(r, clock.today())['due_date']:%m月%d日}"}


class SnoozeIn(BaseModel):
    days: int = Field(default=3, ge=1, le=30)


@router.post("/{rid}/snooze")
def snooze(rid: int, body: SnoozeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = own(db, Routine, rid, user)
    r.snooze_until = clock.today() + timedelta(days=body.days)
    db.commit()
    return public(r, clock.today())


class SubscribedIn(BaseModel):
    accepted: int = Field(default=1, ge=0, le=10)


@router.post("/{rid}/subscribed")
def subscribed(rid: int, body: SubscribedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """前端 wx.requestSubscribeMessage 用户点了允许后调用，攒一次提醒机会。"""
    r = own(db, Routine, rid, user)
    r.reminder_credits = min(20, r.reminder_credits + body.accepted)
    db.commit()
    return public(r, clock.today())


@router.get("/{rid}")
def detail(rid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = own(db, Routine, rid, user)
    today = clock.today()
    logs = []
    for log in r.logs:
        photos = [file_url(db.get(Upload, uid)) for uid in log.photo_upload_ids or []]
        logs.append({"id": log.id, "done_date": log.done_date, "note": log.note, "cost": log.cost, "photos": [p for p in photos if p]})
    avg = average_cycle([l.done_date for l in r.logs])
    suggestion = None
    if avg and abs(avg - r.cycle_days) / r.cycle_days > 0.2:
        suggestion = f"你实际大约每 {avg:g} 天{r.name}一次，要不要把周期改成 {round(avg)} 天？"
    ontime = sorted(l.done_date for l in r.logs)
    due_count = len(ontime) - 1
    on = sum(1 for a, b in zip(ontime, ontime[1:]) if (b - a).days <= r.cycle_days + 2)
    return {**public(r, today), "logs": logs, "average_cycle": avg, "suggestion": suggestion,
            "regularity": round(on / due_count, 2) if due_count > 0 else None}


@router.delete("/{rid}/logs/{log_id}")
def delete_log(rid: int, log_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = own(db, Routine, rid, user)
    log = own(db, RoutineLog, log_id, user)
    if log.routine_id != r.id:
        raise HTTPException(404)
    db.delete(log)
    db.flush()
    r.last_done_date = db.scalar(select(func.max(RoutineLog.done_date)).where(RoutineLog.routine_id == r.id))
    db.commit()
    return {"ok": True}
