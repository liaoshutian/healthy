from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import Session, User, current_user, get_db, tier_of
from app.data.meta import BODY_PARTS, ROUTINE_TEMPLATES, SYMPTOM_TAGS
from app.services import clock, daily, plans, portions
from app.services.membership_benefits import BENEFITS

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/today")
def today(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return daily.today_overview(db, user)


@router.get("/calendar")
def calendar(year: int | None = None, month: int | None = Query(default=None, ge=1, le=12),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = clock.today()
    return daily.calendar_month(db, user, year or t.year, month or t.month)


@router.get("/calendar/day")
def calendar_day(day: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return daily.day_detail(db, user, day)


@router.get("/trends")
def trends(metric: str = "weight_kg", range: str = "month", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if metric not in daily.METRICS or range not in daily.RANGES:
        raise HTTPException(400, "参数不对")
    return daily.trend(db, user, metric, range, tier_of(db, user))


@router.get("/meta")
def meta():
    """小程序启动时拉一次的静态数据。"""
    return {
        "body_parts": BODY_PARTS,
        "symptom_tags": SYMPTOM_TAGS,
        "routine_templates": ROUTINE_TEMPLATES,
        "plans": [plans.plan_public(p) for p in plans.PLANS.values()],
        "portion_references": [{"key": k, "unit": u, "name": n, "icon": i} for k, u, n, i in portions.REFERENCES],
        "petals": [{"key": k, "label": l, "icon": i} for k, l, i in daily.PETALS],
        "metrics": [{"key": k, "label": l, "unit": u} for k, (l, u) in daily.METRICS.items()],
        "benefits": BENEFITS,
    }
