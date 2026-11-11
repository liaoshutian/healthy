"""食物库种子数据的自检：数量、重名、类别和标签合法、热量和三大营养素大致对得上。"""
from types import SimpleNamespace

from app.data.foods import FOODS
from app.services import nutrition

KNOWN_TAGS = {
    "grain", "refined_grain", "whole_grain", "starchy", "red_meat", "poultry", "fish", "egg", "legume",
    "veg", "fruit", "nuts", "dairy", "olive_oil", "sugar", "fried", "processed",
}


def test_food_library_size():
    assert len(FOODS) >= 1000


def test_names_and_aliases_unique():
    seen: dict[str, str] = {}
    for name, aliases, *_ in FOODS:
        assert name not in aliases, name
        for key in [name, *aliases]:
            assert key == key.strip() and " " not in key, key
            assert key not in seen, f"{key} 同时属于 {seen[key]} 和 {name}"
            seen[key] = name


def test_fields_valid():
    for name, aliases, cat, kcal, carb, protein, fat, unit, unit_g, tags in FOODS:
        assert cat in nutrition.CATEGORIES, name
        assert set(tags) <= KNOWN_TAGS, name
        assert 0 < len(name) <= 64 and 0 < len(unit) <= 8, name
        assert unit_g > 0 and min(kcal, carb, protein, fat) >= 0, name
        assert carb + protein + fat <= 100, name


def test_kcal_roughly_matches_macros():
    """4/4/9 估算值和标注千卡大致一致；含酒精的、几乎没热量的跳过。碳水含膳食纤维，所以估算值允许偏高多一些。"""
    for name, aliases, cat, kcal, carb, protein, fat, *_ in FOODS:
        if kcal <= 20 or "酒" in name or any("酒" in a for a in aliases):
            continue
        est = carb * 4 + protein * 4 + fat * 9
        assert -0.2 <= (est - kcal) / kcal <= 0.35, f"{name}: {kcal} vs {est:.0f}"


def test_common_home_dishes_match():
    foods = [SimpleNamespace(name=n, aliases=a) for n, a, *_ in FOODS]
    for q, want in [("韭黄炒蛋", "韭黄炒蛋"), ("韭黄炒鸡蛋", "韭黄炒蛋"), ("西红柿炒鸡蛋", "番茄炒蛋"),
                    ("酸辣土豆丝", "炒土豆丝"), ("一碗螺蛳粉", "螺蛳粉"), ("清炒上海青", "炒青菜")]:
        assert nutrition.match(foods, q).name == want, q
