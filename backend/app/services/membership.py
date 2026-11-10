"""会员：兑换码核销、管理员开通、试用。Subscription 表是唯一依据。"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MembershipLog, RedeemCode, Subscription, User
from app.services import clock

TIERS = ("free", "pro", "max")
# 低档升高档时按剩余天数折算的比例（参考星球侧月价 Pro 18 / Max 38）
TIER_WEIGHT = {"pro": 18, "max": 38}
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 去掉易混的 0/O/1/I


class RedeemError(Exception):
    pass


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def effective_tier(db: Session, user: User) -> tuple[str, datetime | None]:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub and _aware(sub.end_at) > clock.now():
        return sub.tier, sub.end_at
    return "free", None


def grant(db: Session, user: User, tier: str, days: int, source: str, code: str | None = None, note: str | None = None) -> Subscription:
    """开通或顺延。同档顺延；低档升高档时把剩余天数按价格比折算后再加。高档用户兑换低档码则按低档天数折算成高档天数顺延。"""
    if tier not in ("pro", "max"):
        raise ValueError("bad tier")
    now = clock.now()
    # 锁住这个用户，同一用户的并发兑换/开通排队执行，避免互相覆盖到期时间
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id).with_for_update())
    if sub and _aware(sub.end_at) > now:
        remaining = (_aware(sub.end_at) - now).total_seconds() / 86400
        if sub.tier == tier:
            new_tier, total = tier, remaining + days
        elif TIER_WEIGHT[tier] > TIER_WEIGHT[sub.tier]:
            new_tier = tier
            total = remaining * TIER_WEIGHT[sub.tier] / TIER_WEIGHT[tier] + days
        else:
            new_tier = sub.tier
            total = remaining + days * TIER_WEIGHT[tier] / TIER_WEIGHT[sub.tier]
        sub.tier = new_tier
        sub.end_at = now + timedelta(days=total)
    else:
        if sub is None:
            sub = Subscription(user_id=user.id, tier=tier, start_at=now, end_at=now)
            db.add(sub)
        sub.tier, sub.start_at, sub.end_at = tier, now, now + timedelta(days=days)
    db.add(MembershipLog(user_id=user.id, source=source, tier=tier, days=days, code=code, end_at=sub.end_at, note=note))
    return sub


def revoke(db: Session, user: User, note: str | None = None) -> None:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub:
        sub.end_at = clock.now()
        db.add(MembershipLog(user_id=user.id, source="admin", tier=sub.tier, days=0, end_at=sub.end_at, note=note or "撤销"))


def normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def redeem(db: Session, user: User, raw_code: str) -> Subscription:
    code = normalize_code(raw_code)
    rc = db.scalar(select(RedeemCode).where(RedeemCode.code == code).with_for_update())
    if not rc or rc.revoked:
        raise RedeemError("兑换码不存在，检查一下有没有输错")
    if rc.used_by is not None or rc.used_at is not None:
        if rc.used_by == user.id:
            # 幂等：同一个人重复提交不会重复加时长
            return db.scalar(select(Subscription).where(Subscription.user_id == user.id))
        raise RedeemError("这个兑换码已经被用过了")
    if rc.redeem_before and clock.today() > rc.redeem_before:
        raise RedeemError("这个兑换码已过兑换期限")
    rc.used_by, rc.used_at = user.id, clock.now()
    sub = grant(db, user, rc.tier, rc.days, "code", code=code)
    db.commit()
    return sub


def generate_codes(db: Session, tier: str, days: int, count: int, batch: str | None, redeem_before=None) -> list[str]:
    codes = []
    for _ in range(count):
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))
            if not db.scalar(select(RedeemCode.id).where(RedeemCode.code == code)):
                break
        db.add(RedeemCode(code=code, tier=tier, days=days, batch=batch, redeem_before=redeem_before))
        codes.append(code)
    db.commit()
    return codes
