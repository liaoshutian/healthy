from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Upload, User
from app.security import current_user
from app.services.membership import effective_tier

__all__ = ["get_db", "current_user", "Session", "User", "tier_of", "own", "own_upload"]


def tier_of(db: Session, user: User) -> str:
    return effective_tier(db, user)[0]


def own(db: Session, model, obj_id: int, user: User):
    obj = db.get(model, obj_id)
    if not obj or getattr(obj, "user_id", None) != user.id:
        raise HTTPException(404, "没找到这条记录")
    return obj


def own_upload(db: Session, upload_id: int | None, user: User) -> Upload | None:
    if upload_id is None:
        return None
    return own(db, Upload, upload_id, user)


def require_medical_consent(user: User = Depends(current_user)) -> User:
    if not user.medical_consent_at:
        raise HTTPException(428, "记录病历和用药前需要先同意《敏感信息授权》")
    return user
