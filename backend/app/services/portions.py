"""把克和千卡换算成生活里的参照物：碗饭、鸡翅、盘菜、苹果、勺油。

后端一律按克计算，只在展示时换算。换算值为初稿，建议营养师审定（方案 5.2）。
"""

RICE_BOWL_GRAMS = 150  # 1 碗熟米饭
RICE_BOWL_KCAL = 174  # 150 g 米饭的热量，用来说“相当于几碗饭”
WING_PROTEIN_G = 6.0  # 1 只鸡翅中约 35 g，含蛋白质约 6 g
PLATE_GRAMS = 200  # 1 盘家常小盘蔬菜
APPLE_GRAMS = 200  # 1 个苹果
OIL_SPOON_FAT_G = 10  # 1 白瓷汤勺油约 10 g

# 参照物：key, 量词, 名称, 图标
REFERENCES = [
    ("rice", "碗", "饭", "🍚"),
    ("wing", "只", "鸡翅", "🍗"),
    ("plate", "盘", "青菜", "🥬"),
    ("apple", "个", "苹果", "🍎"),
    ("oil", "勺", "油", "🥄"),
]

CATEGORY_GROUP = {
    "staple": "rice",
    "meat": "wing",
    "fish": "wing",
    "egg": "wing",
    "soy": "wing",
    "veg": "plate",
    "fruit": "apple",
    "oil": "oil",
    "nuts": "oil",
    "dairy": "extra",
    "drink": "extra",
    "snack": "extra",
    "other": "extra",
}


def round_half(x: float) -> float:
    """四舍五入到 0.5，方便说“半碗”。很少但不为 0 时记为 0.5。"""
    if x <= 0:
        return 0
    r = round(x * 2) / 2
    return r if r > 0 else 0.5


def fmt_count(x: float) -> str:
    if x == 0.5:
        return "半"
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def item_reference_amount(item: dict) -> tuple[str, float]:
    """返回某条食物对应的参照物组和数量（未取整）。item 需含 category/grams/kcal/protein/fat。"""
    group = CATEGORY_GROUP.get(item["category"], "extra")
    if group == "rice":
        return group, item["kcal"] / RICE_BOWL_KCAL
    if group == "wing":
        return group, item["protein"] / WING_PROTEIN_G
    if group == "plate":
        return group, item["grams"] / PLATE_GRAMS
    if group == "apple":
        return group, item["grams"] / APPLE_GRAMS
    if group == "oil":
        return group, item["fat"] / OIL_SPOON_FAT_G
    return "extra", item["kcal"] / RICE_BOWL_KCAL


def summarize(items: list[dict]) -> dict:
    """把一天（或一顿）的条目汇总成“2 碗饭 · 4 只鸡翅 · 1 盘青菜 · 1 个苹果”。"""
    totals = {key: 0.0 for key, *_ in REFERENCES}
    extra = 0.0
    for it in items:
        group, amount = item_reference_amount(it)
        if group == "extra":
            extra += amount
        else:
            totals[group] += amount
    icons = []
    parts = []
    for key, unit, name, icon in REFERENCES:
        n = round_half(totals[key])
        icons.append({"key": key, "icon": icon, "unit": unit, "name": name, "count": n, "label": f"{fmt_count(n)} {unit}{name}" if n else ""})
        if n:
            parts.append(f"{fmt_count(n)} {unit}{name}")
    extra_bowls = round_half(extra)
    if extra_bowls:
        parts.append(f"零食饮品约 {fmt_count(extra_bowls)} 碗饭")
    return {"text": " · ".join(parts), "icons": icons, "extra_rice_bowls": extra_bowls}


def rice_equivalent_text(kcal: float) -> str:
    """“这杯奶茶大约等于 2 碗饭”。"""
    n = round_half(kcal / RICE_BOWL_KCAL)
    if not n:
        return "几乎没什么热量"
    return f"大约等于 {fmt_count(n)} 碗饭"


def item_display(name: str, unit_name: str, unit_count: float) -> str:
    """优先用食物自己的量词：“4 只鸡翅”“6 块红烧肉”。"""
    return f"{fmt_count(round_half(unit_count))} {unit_name}{name}"
