import hashlib
import hmac
import io
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps

from app.api.deps import Session, User, current_user, get_db, own
from app.config import get_settings
from app.models import Upload
from app.services.storage import LocalStorage, get_storage, new_key

router = APIRouter(tags=["uploads"])
KINDS = {"food", "inbody", "medicine", "medical", "routine", "avatar"}
MAX_BYTES = 10 * 1024 * 1024
MAX_SIDE = 2048


def compress(data: bytes) -> tuple[bytes, str]:
    """转成 JPEG、长边压到 2048px，并按 EXIF 转正。"""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception:
        raise HTTPException(400, "这不是一张图片")
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue(), "image/jpeg"


def _sign(key: str, exp: int) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def file_url(up: Upload | None) -> str | None:
    if up is None:
        return None
    storage = get_storage()
    if isinstance(storage, LocalStorage):
        exp = int(time.time()) + 3600
        return f"{storage.url(up.key)}?exp={exp}&sig={_sign(up.key, exp)}"
    return storage.url(up.key)


@router.post("/api/uploads")
async def upload(
    kind: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if kind not in KINDS:
        raise HTTPException(400, "kind 不对")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "图片太大了，换一张小一点的")
    data, ctype = compress(data)
    key = new_key(user.id, kind, "jpg")
    get_storage().put(key, data, ctype)
    up = Upload(user_id=user.id, kind=kind, key=key, content_type=ctype, size=len(data))
    db.add(up)
    db.commit()
    return {"id": up.id, "url": file_url(up)}


@router.delete("/api/uploads/{upload_id}")
def delete_upload(upload_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    up = own(db, Upload, upload_id, user)
    get_storage().delete(up.key)
    db.delete(up)
    db.commit()
    return {"ok": True}


@router.get("/api/files/{key:path}")
def local_file(key: str, exp: int, sig: str):
    """仅本地存储使用：带签名的临时链接（小程序 <image> 不能带登录头）。"""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404)
    if exp < time.time() or not hmac.compare_digest(sig, _sign(key, exp)):
        raise HTTPException(403, "链接已过期")
    try:
        return Response(storage.get(key), media_type="image/jpeg")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404)
