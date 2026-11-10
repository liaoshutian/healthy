from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Session, get_db
from app.config import get_settings
from app.models import User
from app.security import create_token
from app.services import membership
from app.services.wechat import WechatError, code2session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    code: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """wx.login 拿到的 code 换 openid，发自己的 JWT。新用户送 7 天 Pro 试用。"""
    try:
        info = code2session(body.code)
    except WechatError as e:
        raise HTTPException(400, str(e))
    user = db.scalar(select(User).where(User.openid == info["openid"]))
    is_new = user is None
    if is_new:
        user = User(openid=info["openid"], unionid=info.get("unionid"))
        db.add(user)
        db.flush()
        days = get_settings().trial_days
        if days > 0:
            membership.grant(db, user, "pro", days, "trial", note="新用户试用")
    elif info.get("unionid") and not user.unionid:
        user.unionid = info["unionid"]
    db.commit()
    return {"token": create_token(user.id), "user_id": user.id, "is_new": is_new, "onboarded": user.onboarded}
