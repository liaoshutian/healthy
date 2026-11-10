"""图片存储：开发用本地磁盘，生产用腾讯云 COS（私有读 + 临时签名链接）。"""
import os
import uuid
from datetime import datetime

from app.config import get_settings


class Storage:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def url(self, key: str, expires: int = 3600) -> str:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: str, base_url: str):
        self.root = root
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> str:
        path = os.path.normpath(os.path.join(self.root, key))
        if not path.startswith(os.path.normpath(self.root)):
            raise ValueError("bad key")
        return path

    def put(self, key, data, content_type):
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get(self, key):
        with open(self._path(key), "rb") as f:
            return f.read()

    def delete(self, key):
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def url(self, key, expires=3600):
        # 本地开发时由 /api/files 路由按登录态返回
        return f"{self.base_url}/api/files/{key}"


class COSStorage(Storage):
    def __init__(self, s):
        from qcloud_cos import CosConfig, CosS3Client

        cfg = CosConfig(Region=s.cos_region, SecretId=s.cos_secret_id, SecretKey=s.cos_secret_key, Scheme="https")
        self.client = CosS3Client(cfg)
        self.bucket = s.cos_bucket

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key):
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].get_raw_stream().read()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key, expires=3600):
        return self.client.get_presigned_url(Method="GET", Bucket=self.bucket, Key=key, Expired=expires)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        if s.storage_backend == "cos":
            _storage = COSStorage(s)
        else:
            _storage = LocalStorage(s.local_storage_dir, s.public_base_url)
    return _storage


def new_key(user_id: int, kind: str, ext: str) -> str:
    return f"u/{user_id}/{kind}/{datetime.now():%Y%m}/{uuid.uuid4().hex}.{ext}"
