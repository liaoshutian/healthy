import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api import admin, auth, body, challenges, health, me, meals, membership, overview, routines, uploads
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")



@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db import Base, SessionLocal, engine
    from app.services.nutrition import seed_foods

    if get_settings().env == "dev":
        Base.metadata.create_all(engine)  # 生产环境用 alembic upgrade head
    with SessionLocal() as db:
        n = seed_foods(db)
        if n:
            logging.getLogger(__name__).info("食物库新增 %d 条", n)
    yield


app = FastAPI(title="青柠生活 API", version="0.1.0", lifespan=lifespan,
              docs_url="/api/docs" if get_settings().env == "dev" else None)

for r in (auth, me, uploads, meals, challenges, body, routines, health, overview, membership, admin):
    app.include_router(r.router)


@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(Path(__file__).parent / "static" / "admin.html")
