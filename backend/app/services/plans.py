"""饮食方案（挑战卡）定义与打分。方案 5.3 + 4.9 节。

每个方案 = 宏量比例区间 + 禁忌/推荐食物标签。打分口径：宏量 50 + 禁忌 30 + 推荐 20，
70 分以上这顿饭就“点亮”方案图标，一天点亮 2 顿算“今日达成”。不说“超标”“失败”。
"""
from dataclasses import dataclass, field

LIT_THRESHOLD = 70
DAY_GOAL_LIT_MEALS = 2


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    icon: str
    lit_icon_name: str
    tagline: str
    how_to_play: list[str]
    difficulty: int  # 1-3
    suggested_days: int
    # 宏量占总热量的比例区间（百分比），None = 不限
    carb: tuple[float, float] | None = None
    protein: tuple[float, float] | None = None
    fat: tuple[float, float] | None = None
    avoid_tags: frozenset[str] = field(default_factory=frozenset)
    prefer_tags: frozenset[str] = field(default_factory=frozenset)
    caution: str | None = None


PLANS: dict[str, Plan] = {
    p.code: p
    for p in [
        Plan(
            code="balanced",
            name="均衡饮食",
            icon="🍱",
            lit_icon_name="一颗饭团",
            tagline="什么都吃一点，最好坚持的玩法",
            how_to_play=["每顿有主食、有肉蛋豆、有青菜", "一天大约 2–3 碗饭、4–6 只鸡翅的肉蛋豆、2 盘青菜、1 个苹果"],
            difficulty=1,
            suggested_days=21,
            carb=(50, 65),
            protein=(10, 20),
            fat=(20, 30),
            prefer_tags=frozenset({"veg", "fruit", "whole_grain", "fish", "legume"}),
            avoid_tags=frozenset({"sugar", "fried"}),
        ),
        Plan(
            code="low_carb",
            name="低碳水",
            icon="🥦",
            lit_icon_name="一朵西兰花",
            tagline="主食少一点，菜和肉多一点",
            how_to_play=["每天主食不超过 1 碗饭", "含糖饮料换成茶或气泡水", "饿了就多吃青菜和鸡蛋"],
            difficulty=1,
            suggested_days=14,
            carb=(0, 26),
            prefer_tags=frozenset({"veg", "egg", "fish", "poultry"}),
            avoid_tags=frozenset({"refined_grain", "sugar"}),
        ),
        Plan(
            code="keto",
            name="生酮",
            icon="🥑",
            lit_icon_name="一颗牛油果",
            tagline="几乎不吃主食，靠肉蛋和好油吃饱",
            how_to_play=["每天碳水大约不超过半碗饭的量", "不吃米面、糖、多数水果和土豆红薯", "多吃肉蛋鱼、青菜、牛油果和坚果"],
            difficulty=3,
            suggested_days=14,
            carb=(0, 10),
            fat=(65, 80),
            prefer_tags=frozenset({"egg", "fish", "olive_oil", "nuts", "veg"}),
            avoid_tags=frozenset({"grain", "sugar", "starchy", "fruit"}),
            caution="怀孕、正在用降糖药、有肝肾疾病的朋友不建议玩这张卡，先问问医生。",
        ),
        Plan(
            code="paleo",
            name="原始人",
            icon="🍖",
            lit_icon_name="一根骨头",
            tagline="只吃“原始人也能找到”的食物",
            how_to_play=["吃肉蛋鱼、蔬菜水果、坚果", "不吃谷物、豆类、奶制品、糖和加工食品"],
            difficulty=2,
            suggested_days=21,
            prefer_tags=frozenset({"veg", "fruit", "fish", "egg", "poultry", "red_meat", "nuts"}),
            avoid_tags=frozenset({"grain", "legume", "dairy", "sugar", "processed"}),
        ),
        Plan(
            code="mediterranean",
            name="地中海",
            icon="🫒",
            lit_icon_name="一片橄榄叶",
            tagline="多鱼多菜、用好油，口碑最稳的一张卡",
            how_to_play=["每周吃两三次鱼", "主食换成杂粮，红肉少一点", "炒菜用橄榄油，零食换成坚果"],
            difficulty=1,
            suggested_days=21,
            fat=(30, 40),
            prefer_tags=frozenset({"fish", "olive_oil", "whole_grain", "veg", "fruit", "nuts", "legume"}),
            avoid_tags=frozenset({"red_meat", "processed", "sugar"}),
        ),
    ]
}

# 下次可以试的替换建议（按禁忌标签）
SWAPS = {
    "refined_grain": "下次可以把白米饭换成花菜饭，或者多来一盘青菜",
    "grain": "下次可以把米饭面条换成花菜饭，或者多来一盘青菜、一份蛋",
    "sugar": "甜饮料可以换成无糖茶或气泡水",
    "starchy": "土豆红薯可以换成西兰花或蘑菇",
    "fruit": "水果可以换成几颗草莓或蓝莓，或者干脆换成黄瓜",
    "legume": "豆制品可以换成鸡蛋或鱼",
    "dairy": "奶制品可以换成一小把坚果",
    "processed": "加工食品可以换成新鲜的肉蛋",
    "red_meat": "红肉可以换成鱼或鸡肉",
    "fried": "炸的可以换成蒸的或烤的",
}


def macro_pcts(carb: float, protein: float, fat: float) -> dict[str, float]:
    kcal = carb * 4 + protein * 4 + fat * 9
    if kcal <= 0:
        return {"carb": 0, "protein": 0, "fat": 0}
    return {"carb": carb * 4 / kcal * 100, "protein": protein * 4 / kcal * 100, "fat": fat * 9 / kcal * 100}


def _deviation(value: float, rng: tuple[float, float] | None) -> float:
    if rng is None:
        return 0
    lo, hi = rng
    if value < lo:
        return lo - value
    if value > hi:
        return value - hi
    return 0


def score_items(plan: Plan, items: list[dict]) -> dict:
    """给一组食物条目（一顿或一天）打分。items 需含 name/kcal/carb/protein/fat/tags。"""
    total_kcal = sum(i["kcal"] for i in items)
    if not items or total_kcal <= 0:
        return {"score": 0, "lit": False, "tip": None, "reasons": []}
    pct = macro_pcts(sum(i["carb"] for i in items), sum(i["protein"] for i in items), sum(i["fat"] for i in items))
    reasons: list[str] = []
    tip = None

    devs = {m: _deviation(pct[m], getattr(plan, m)) for m in ("carb", "protein", "fat")}
    macro_score = max(0.0, 50 - 2 * sum(devs.values()))

    avoid_kcal = 0.0
    worst: tuple[float, str, str] | None = None
    for it in items:
        hit = sorted((t for t in it.get("tags", []) if t in plan.avoid_tags), key=lambda t: list(SWAPS).index(t) if t in SWAPS else 99)
        if hit:
            avoid_kcal += it["kcal"]
            if worst is None or it["kcal"] > worst[0]:
                worst = (it["kcal"], it["name"], hit[0])
    avoid_score = 30 * max(0.0, 1 - 2 * avoid_kcal / total_kcal)

    prefer_kcal = sum(it["kcal"] for it in items if any(t in plan.prefer_tags for t in it.get("tags", [])))
    has_prefer = any(any(t in plan.prefer_tags for t in it.get("tags", [])) for it in items)
    prefer_score = 20 * min(1.0, 2 * prefer_kcal / total_kcal) if prefer_kcal else (10 if has_prefer else 0)
    if not plan.prefer_tags:
        prefer_score = 20

    if worst:
        reasons.append(f"{worst[1]}不在{plan.name}的菜单里")
        tip = SWAPS.get(worst[2])
    if devs["carb"] > 0 and pct["carb"] > (plan.carb or (0, 100))[1]:
        reasons.append("主食多了一点")
        tip = tip or "下次主食可以少半碗，换成青菜或鸡蛋"
    if devs["protein"] > 0 and pct["protein"] < (plan.protein or (0, 100))[0]:
        reasons.append("肉蛋豆少了一点")
        tip = tip or "可以加一个鸡蛋或几只鸡翅"
    if devs["fat"] > 0 and pct["fat"] < (plan.fat or (0, 100))[0]:
        reasons.append("好油少了一点")
        tip = tip or "可以加半个牛油果或一小把坚果"
    if devs["fat"] > 0 and pct["fat"] > (plan.fat or (0, 100))[1]:
        reasons.append("油多了一点")
        tip = tip or "下次可以试试蒸或煮的做法"

    score = int(round(macro_score + avoid_score + prefer_score))
    return {"score": score, "lit": score >= LIT_THRESHOLD, "tip": tip, "reasons": reasons, "macro_pct": {k: round(v) for k, v in pct.items()}}


def plan_public(plan: Plan) -> dict:
    return {
        "code": plan.code,
        "name": plan.name,
        "icon": plan.icon,
        "lit_icon_name": plan.lit_icon_name,
        "tagline": plan.tagline,
        "how_to_play": plan.how_to_play,
        "difficulty": plan.difficulty,
        "suggested_days": plan.suggested_days,
        "caution": plan.caution,
    }


def recommend(meals_items: list[list[dict]]) -> dict | None:
    """用过去的饭推荐玩法：哪张卡和你现在的饮食最像。meals_items 为每顿饭的条目列表。"""
    meals_items = [m for m in meals_items if m]
    if len(meals_items) < 3:
        return None
    best = None
    for plan in PLANS.values():
        lit = sum(1 for m in meals_items if score_items(plan, m)["lit"])
        ratio = lit / len(meals_items)
        if best is None or ratio > best[1]:
            best = (plan, ratio)
    plan, ratio = best
    tenths = max(1, round(ratio * 10))
    return {
        "plan": plan_public(plan),
        "similarity": round(ratio, 2),
        "text": f"你最近的饮食已经有 {tenths} 成像{plan.name}了，要不要试试这张卡？",
    }
