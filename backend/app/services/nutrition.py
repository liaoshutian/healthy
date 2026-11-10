"""食物库匹配与营养计算：库里每 100g 营养素 × 克重。库里没有的用模型估值，标记为估算并进待审队列。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Food
from app.services import portions

CATEGORIES = {"staple", "meat", "fish", "egg", "soy", "veg", "fruit", "oil", "nuts", "dairy", "drink", "snack", "other"}
# 估不出来时的保底值（每 100 g）
DEFAULT_PER100 = {
    "staple": (150, 30, 4, 2), "meat": (220, 3, 18, 15), "fish": (120, 1, 18, 5), "egg": (140, 2, 12, 9),
    "soy": (110, 5, 9, 6), "veg": (45, 4, 2, 2.5), "fruit": (50, 12, 0.6, 0.2), "oil": (899, 0, 0, 100),
    "nuts": (600, 20, 18, 50), "dairy": (70, 5, 3.3, 3.5), "drink": (40, 10, 0, 0), "snack": (450, 60, 6, 20),
    "other": (150, 15, 6, 7),
}


def _norm(s: str) -> str:
    return s.strip().replace(" ", "")


def all_foods(db: Session) -> list[Food]:
    return list(db.scalars(select(Food)))


def match(foods: list[Food], name: str, candidates: list[str] | None = None) -> Food | None:
    names = [_norm(name)] + [_norm(c) for c in (candidates or []) if c]
    for n in names:
        for f in foods:
            if n == f.name or n in (f.aliases or []):
                return f
    # 包含关系：“清炒上海青”→“炒青菜”的别名“上海青”
    for n in names[:1]:
        best = None
        for f in foods:
            for key in [f.name, *(f.aliases or [])]:
                if len(key) >= 2 and key in n and (best is None or len(key) > best[0]):
                    best = (len(key), f)
        if best:
            return best[1]
    return None


def build_item(
    food: Food | None,
    name: str,
    grams: float | None = None,
    count: float | None = None,
    unit: str | None = None,
    category: str | None = None,
    per100g: dict | None = None,
) -> dict:
    """返回一条可保存的食物条目。grams 和 count 至少给一个。"""
    if food:
        if grams is None:
            grams = (count or 1) * food.unit_grams
        kcal, carb, protein, fat = food.kcal, food.carb, food.protein, food.fat
        unit_name = food.unit_name
        unit_count = count if (count and unit == food.unit_name) else grams / food.unit_grams
        cat, tags, estimated = food.category, list(food.tags or []), False
        display_name = food.name if _norm(name) in (food.name, *(food.aliases or [])) else name
    else:
        cat = category if category in CATEGORIES else "other"
        d = DEFAULT_PER100[cat]
        p = per100g or {}

        def pick(key, default):
            try:
                v = float(p.get(key))
                return v if v >= 0 else default
            except (TypeError, ValueError):
                return default

        kcal, carb, protein, fat = pick("kcal", d[0]), pick("carb", d[1]), pick("protein", d[2]), pick("fat", d[3])
        grams = grams if grams is not None else (count or 1) * 100
        unit_name = unit or "份"
        unit_count = count or 1
        tags, estimated, display_name = [], True, name
    f = grams / 100
    item = {
        "food_id": food.id if food else None,
        "name": display_name,
        "category": cat,
        "grams": round(grams, 1),
        "unit_name": unit_name,
        "unit_count": round(unit_count, 2),
        "kcal": round(kcal * f, 1),
        "carb": round(carb * f, 1),
        "protein": round(protein * f, 1),
        "fat": round(fat * f, 1),
        "tags": tags,
        "estimated": estimated,
    }
    return decorate(item)


def decorate(item: dict) -> dict:
    """附上给人看的文字：“4 只鸡翅”“大约等于 2 碗饭”。"""
    item["display"] = portions.item_display(item["name"], item["unit_name"], item["unit_count"])
    if item["category"] in ("drink", "snack", "dairy"):
        item["rice_equivalent"] = portions.rice_equivalent_text(item["kcal"])
    return item


def queue_unknown(db: Session, item: dict, per100g: dict | None) -> None:
    """库里没有的食物用模型估值补进库，verified=False，等人工审核。"""
    if not item["estimated"] or not per100g:
        return
    if db.scalar(select(Food.id).where(Food.name == item["name"])):
        return
    g = item["grams"] / 100 or 1
    db.add(Food(name=item["name"], aliases=[], category=item["category"], kcal=item["kcal"] / g, carb=item["carb"] / g,
                protein=item["protein"] / g, fat=item["fat"] / g, unit_name=item["unit_name"],
                unit_grams=max(1.0, item["grams"] / (item["unit_count"] or 1)), tags=[], verified=False))


def seed_foods(db: Session) -> int:
    from app.data.foods import FOODS

    existing = {n for (n,) in db.execute(select(Food.name))}
    added = 0
    for name, aliases, cat, kcal, carb, protein, fat, unit, unit_g, tags in FOODS:
        if name in existing:
            continue
        db.add(Food(name=name, aliases=aliases, category=cat, kcal=kcal, carb=carb, protein=protein, fat=fat,
                    unit_name=unit, unit_grams=unit_g, tags=tags, verified=True))
        added += 1
    db.commit()
    return added
