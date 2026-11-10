from app.services import plans, portions


def item(name, category, grams, kcal, carb, protein, fat, tags=()):
    return {"name": name, "category": category, "grams": grams, "kcal": kcal, "carb": carb, "protein": protein, "fat": fat, "tags": list(tags)}


RICE = item("米饭", "staple", 300, 348, 77.7, 7.8, 0.9, ["grain", "refined_grain"])
WINGS = item("鸡翅", "meat", 140, 294, 1.4, 24.4, 21, ["poultry"])
VEG = item("炒青菜", "veg", 200, 90, 6, 3, 6, ["veg"])
APPLE = item("苹果", "fruit", 200, 106, 27.4, 0.8, 0.4, ["fruit"])
TEA = item("奶茶", "drink", 500, 300, 50, 3, 10, ["sugar", "processed", "dairy"])


def test_summary_uses_everyday_units():
    s = portions.summarize([RICE, WINGS, VEG, APPLE])
    assert s["text"] == "2 碗饭 · 4 只鸡翅 · 1 盘青菜 · 1 个苹果"


def test_snacks_shown_as_rice_bowls():
    assert portions.rice_equivalent_text(300) == "大约等于 1.5 碗饭"
    assert "零食饮品约 1.5 碗饭" in portions.summarize([TEA])["text"]


def test_half_portions():
    assert portions.fmt_count(portions.round_half(0.3)) == "半"


def test_keto_lights_up_for_meat_and_veg_not_for_rice():
    keto = plans.PLANS["keto"]
    good = plans.score_items(keto, [WINGS, VEG, item("牛油果", "fruit", 75, 128, 5.5, 1.5, 11.5, ["fruit"])])
    bad = plans.score_items(keto, [RICE, VEG])
    assert bad["score"] < good["score"]
    assert not bad["lit"]
    assert "花菜饭" in bad["tip"]


def test_no_harsh_words_in_tips():
    for plan in plans.PLANS.values():
        r = plans.score_items(plan, [RICE, TEA])
        for text in [r["tip"] or "", *r["reasons"]]:
            assert "超标" not in text and "失败" not in text


def test_recommend_needs_three_meals():
    assert plans.recommend([[RICE]]) is None
    rec = plans.recommend([[RICE, WINGS, VEG], [RICE, VEG, APPLE], [WINGS, VEG]])
    assert rec and "成像" in rec["text"]
