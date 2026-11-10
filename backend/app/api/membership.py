from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import Session, User, current_user, get_db
from app.services import clock, membership, quota
from app.services.membership_benefits import BENEFITS

router = APIRouter(prefix="/api/membership", tags=["membership"])


def state(db: Session, user: User) -> dict:
    tier, end_at = membership.effective_tier(db, user)
    days_left = None
    if end_at:
        end = end_at if end_at.tzinfo else end_at.replace(tzinfo=clock.TZ)
        days_left = max(0, (end - clock.now()).days)
    return {"tier": tier, "end_at": end_at, "days_left": days_left, "member_id": f"QN{user.id:06d}",
            "quotas": [quota.usage(f, user.id, tier, clock.today()) for f in quota.LIMITS], "benefits": BENEFITS}


@router.get("")
def get_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return state(db, user)


class RedeemIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)


@router.post("/redeem")
def redeem(body: RedeemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        membership.redeem(db, user, body.code)
    except membership.RedeemError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return {**state(db, user), "message": "兑换成功，已经生效啦"}
