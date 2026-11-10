import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["LOCAL_STORAGE_DIR"] = f"{_tmp}/uploads"
os.environ["ENV"] = "dev"
os.environ["ADMIN_TOKEN"] = "admin-secret"
os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ["OPENAI_BASE_URL"] = "https://relay.test/v1"
os.environ["QWEN_API_KEY"] = "qwen-test"
os.environ["DEEPSEEK_API_KEY"] = "ds-test"
os.environ["REDIS_URL"] = ""

import io  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import quota  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    quota.set_counter(quota._MemoryCounter())
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, code="alice"):
    r = client.post("/api/auth/login", json={"code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def auth(client):
    return login(client)


def jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 200, 80)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def fake_ai(monkeypatch):
    """按 provider 名返回预设结果；值是 Exception 时抛出。"""
    from app.services.ai import service

    responses: dict[str, object] = {}
    calls: list[str] = []

    def fake_chat_json(provider, system, content, timeout=None):
        calls.append(provider.name)
        r = responses.get(provider.name)
        if isinstance(r, Exception):
            raise r
        if r is None:
            from app.services.ai.client import AIError

            raise AIError("no fake response")
        return r

    monkeypatch.setattr(service, "chat_json", fake_chat_json)
    return responses, calls
