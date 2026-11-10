from datetime import date

DateT = date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Session, User, current_user, get_db, own, own_upload, tier_of
from app.api.uploads import file_url
from app.models import Food, MealItem, MealLog, Upload, WaterLog
from app.services import clock, daily, nutrition, plans, portions, quota
from app.services.ai.service import AllProvidersFailed, parse_meal_text, recognize_food
from app.services.storage import get_storage

router = APIRouter(prefix="/api", tags=["meals"])
MEAL_TYPE_PATTERN = "^(breakfast|lunch|dinner|snack)$"


class ItemIn(BaseModel):
    food_id: int | None = None
    name: str = Field(min_length=1, max_length=64)
    grams: float | None = Field(default=None, gt=0, le=5000)
    count: float | None = Field(default=None, gt=0, le=200)
    unit: str | None = Field(default=None, max_length=8)
    category: str | None = None
    per100g: dict | None = None


def guess_meal_type(now=None) -> str:
    h = (now or clock.now()).hour
    if 5 <= h < 10:
        return "breakfast"
    if 10 <= h < 15:
        return "lunch"
    if 17 <= h < 21:
        return "dinner"
    return "snack"


def build_items(db: Session, items: list[ItemIn]) -> list[dict]:
    foods = nutrition.all_foods(db)
    out = []
    for it in items:
        food = db.get(Food, it.food_id) if it.food_id else nutrition.match(foods, it.name)
        out.append(nutrition.build_item(food, it.name, it.grams, it.count, it.unit, it.category, it.per100g))
    return out


def score_for(db: Session, user: User, items: list[dict]) -> dict | None:
    """有进行中的挑战才打分。Free 只看点没点亮，Pro 才有原因和替换建议。"""
    ch = daily.active_challenge(db, user)
    if not ch or not items:
        return None
    plan = plans.PLANS[ch.plan_code]
    result = plans.score_items(plan, items)
    result["plan_code"] = plan.code
    result["plan_name"] = plan.name
    result["lit_icon_name"] = plan.lit_icon_name
    if tier_of(db, user) == "free":
        result["reasons"], result["tip"], result["locked"] = [], None, True
    return result


def draft_response(db: Session, user: User, items: list[dict], extra: dict | None = None) -> dict:
    return {
        "items": items,
        "summary": portions.summarize(items),
        "kcal": round(sum(i["kcal"] for i in items)),
        "carb": round(sum(i["carb"] for i in items)),
        "protein": round(sum(i["protein"] for i in items)),
        "fat": round(sum(i["fat"] for i in items)),
        "score": score_for(db, user, items),
        "suggested_meal_type": guess_meal_type(),
        **(extra or {}),
    }


class RecognizeIn(BaseModel):
    upload_id: int


@router.post("/meals/recognize")
def recognize(body: RecognizeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """拍食物 → 草稿。识别失败或配额用完时返回 fallback=search，前端转到食物库搜索，永远不堵死记录。"""
    up: Upload = own_upload(db, body.upload_id, user)
    tier, today = tier_of(db, user), clock.today()
    if not quota.try_consume("food", user.id, tier, today):
        return {"fallback": "search", "reason": "quota", "message": "今天的拍照识别次数用完啦，可以搜一下食物手动记"}
    try:
        data, provider = recognize_food(db, user.id, get_storage().get(up.key), up.content_type)
    except AllProvidersFailed:
        quota.refund("food", user.id, today)
        return {"fallback": "search", "reason": "ai_failed", "message": "没认出来，换个角度再拍一张，或者搜一下手动记"}
    if not data["is_food"]:
        quota.refund("food", user.id, today)
        return {"fallback": "search", "reason": "not_food", "message": "照片里好像没有吃的，再拍一张试试？"}
    foods = nutrition.all_foods(db)
    items = []
    for raw in data["items"]:
        food = nutrition.match(foods, raw["name"], raw["candidates"])
        item = nutrition.build_item(food, raw["name"], raw["grams"], raw["count"], raw["unit"], raw.get("category"), raw.get("per100g"))
        item.update({"candidates": raw["candidates"], "x": raw.get("x"), "y": raw.get("y"), "per100g": raw.get("per100g")})
        items.append(item)
    return draft_response(db, user, items, {"provider": provider, "photo_upload_id": up.id, "photo_url": file_url(up)})


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)


@router.post("/meals/parse-text")
def parse_text(body: TextIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """“一碗牛肉面加个蛋” → 草稿。"""
    try:
        data, _ = parse_meal_text(db, user.id, body.text)
    except AllProvidersFailed:
        return {"fallback": "search", "reason": "ai_failed", "message": "没看懂，搜一下食物手动记吧"}
    items = [ItemIn(name=r["name"][:64], grams=r["grams"], count=r["count"], unit=(r["unit"] or None) and str(r["unit"])[:8],
                    category=r.get("category"), per100g=r.get("per100g")) for r in data["items"]]
    built = build_items(db, items)
    for b, i in zip(built, items):
        b["per100g"] = i.per100g
    return draft_response(db, user, built)


class PreviewIn(BaseModel):
    items: list[ItemIn] = Field(max_length=30)


@router.post("/meals/preview")
def preview(body: PreviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """确认卡上调份量、改名称时重算。"""
    return draft_response(db, user, build_items(db, body.items))


class MealIn(BaseModel):
    date: DateT | None = None
    meal_type: str = Field(pattern=MEAL_TYPE_PATTERN)
    items: list[ItemIn] = Field(min_length=1, max_length=30)
    photo_upload_id: int | None = None
    source: str = Field(default="manual", pattern="^(photo|manual|copy|text)$")
    note: str | None = Field(default=None, max_length=200)


def _apply(db: Session, user: User, meal: MealLog, body: MealIn) -> dict:
    items = build_items(db, body.items)
    for raw, built in zip(body.items, items):
        if built["estimated"]:
            nutrition.queue_unknown(db, built, raw.per100g)
    meal.items.clear()
    for it in items:
        meal.items.append(MealItem(**{k: it[k] for k in ("food_id", "name", "category", "grams", "unit_name", "unit_count",
                                                          "kcal", "carb", "protein", "fat", "tags", "estimated")}))
    meal.kcal = sum(i["kcal"] for i in items)
    meal.carb = sum(i["carb"] for i in items)
    meal.protein = sum(i["protein"] for i in items)
    meal.fat = sum(i["fat"] for i in items)
    ch = daily.active_challenge(db, user)
    if ch:
        sc = plans.score_items(plans.PLANS[ch.plan_code], items)
        meal.plan_code, meal.plan_score, meal.plan_lit, meal.plan_tip = ch.plan_code, sc["score"], sc["lit"], sc["tip"]
    else:
        meal.plan_code, meal.plan_score, meal.plan_lit, meal.plan_tip = None, None, False, None
    return draft_response(db, user, items)


@router.post("/meals")
def create_meal(body: MealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    own_upload(db, body.photo_upload_id, user)
    meal = MealLog(user_id=user.id, date=body.date or clock.today(), meal_type=body.meal_type, source=body.source,
                   photo_upload_id=body.photo_upload_id, note=body.note)
    db.add(meal)
    result = _apply(db, user, meal, body)
    db.commit()
    return {"id": meal.id, **result, "cheer": cheer(meal)}


def cheer(meal: MealLog) -> str:
    """保存时的一句随机夸夸。"""
    import random

    lines = ["记好啦，今天的饭看起来很不错", "又点亮一瓣青柠", "小柠记下来了", "好好吃饭的人运气不会差", "这顿很有生活气息"]
    if meal.plan_lit:
        lines = ["点亮了一个挑战图标", "这顿很合挑战的口味", "离今日达成又近一步"]
    return random.choice(lines)


@router.get("/meals")
def list_meals(day: date | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = day or clock.today()
    meals = db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.date == d).order_by(MealLog.id))
    return [daily.meal_brief(m) for m in meals]


@router.get("/meals/recent")
def recent_meals(meal_type: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """“和昨天早餐一样”：最近几顿，用于一键复用。"""
    q = select(MealLog).where(MealLog.user_id == user.id)
    if meal_type:
        q = q.where(MealLog.meal_type == meal_type)
    meals = db.scalars(q.order_by(MealLog.date.desc(), MealLog.id.desc()).limit(5))
    return [{**daily.meal_brief(m), "date": m.date} for m in meals]


def meal_detail(db: Session, user: User, m: MealLog) -> dict:
    items = [{"id": i.id, "food_id": i.food_id, "name": i.name, "category": i.category, "grams": i.grams,
              "unit_name": i.unit_name, "unit_count": i.unit_count, "kcal": i.kcal, "carb": i.carb,
              "protein": i.protein, "fat": i.fat, "tags": i.tags, "estimated": i.estimated} for i in m.items]
    for i in items:
        nutrition.decorate(i)
    return {"id": m.id, "date": m.date, "meal_type": m.meal_type, "source": m.source, "note": m.note,
            "photo_upload_id": m.photo_upload_id, "photo_url": file_url(db.get(Upload, m.photo_upload_id)) if m.photo_upload_id else None,
            "items": items, "summary": portions.summarize(items), "kcal": round(m.kcal), "carb": round(m.carb),
            "protein": round(m.protein), "fat": round(m.fat), "plan_code": m.plan_code, "plan_lit": m.plan_lit,
            "plan_tip": m.plan_tip if tier_of(db, user) != "free" else None}


@router.get("/meals/{meal_id}")
def get_meal(meal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return meal_detail(db, user, own(db, MealLog, meal_id, user))


@router.put("/meals/{meal_id}")
def update_meal(meal_id: int, body: MealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meal = own(db, MealLog, meal_id, user)
    own_upload(db, body.photo_upload_id, user)
    meal.meal_type, meal.note, meal.photo_upload_id = body.meal_type, body.note, body.photo_upload_id
    if body.date:
        meal.date = body.date
    result = _apply(db, user, meal, body)
    db.commit()
    return {"id": meal.id, **result}


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(own(db, MealLog, meal_id, user))
    db.commit()
    return {"ok": True}


class CopyIn(BaseModel):
    date: DateT | None = None
    meal_type: str = Field(pattern=MEAL_TYPE_PATTERN)


@router.post("/meals/{meal_id}/copy")
def copy_meal(meal_id: int, body: CopyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    src = own(db, MealLog, meal_id, user)
    items = [ItemIn(food_id=i.food_id, name=i.name, grams=i.grams, category=i.category,
                    per100g={"kcal": i.kcal / i.grams * 100, "carb": i.carb / i.grams * 100,
                             "protein": i.protein / i.grams * 100, "fat": i.fat / i.grams * 100} if i.estimated else None)
             for i in src.items]
    return create_meal(MealIn(date=body.date, meal_type=body.meal_type, items=items, source="copy"), user, db)


# ---------- 食物库 ----------

@router.get("/foods/search")
def search_foods(q: str = "", category: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Food).where(Food.verified.is_(True))
    if category:
        stmt = stmt.where(Food.category == category)
    foods = list(db.scalars(stmt))
    q = q.strip()
    if q:
        foods = [f for f in foods if q in f.name or any(q in a for a in (f.aliases or []))]
        foods.sort(key=lambda f: (f.name != q, len(f.name)))
    return [{"id": f.id, "name": f.name, "category": f.category, "unit_name": f.unit_name, "unit_grams": f.unit_grams,
             "kcal_per_unit": round(f.kcal * f.unit_grams / 100)} for f in foods[:30]]


# ---------- 喝水 ----------

class WaterIn(BaseModel):
    delta: int = Field(ge=-10, le=10)
    date: DateT | None = None


@router.post("/water")
def add_water(body: WaterIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = body.date or clock.today()
    w = db.scalar(select(WaterLog).where(WaterLog.user_id == user.id, WaterLog.date == d))
    if not w:
        w = WaterLog(user_id=user.id, date=d, cups=0)
        db.add(w)
    w.cups = max(0, (w.cups or 0) + body.delta)
    db.commit()
    return {"date": d, "cups": w.cups}
