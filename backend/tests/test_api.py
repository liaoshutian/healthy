from datetime import timedelta

from app.services import clock, quota
from app.services.ai.client import AIError
from tests.conftest import jpeg_bytes, login

ADMIN = {"X-Admin-Token": "admin-secret"}


def upload(client, auth, kind="food"):
    r = client.post("/api/uploads", headers=auth, data={"kind": kind}, files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()


def downgrade_to_free(client, auth):
    me = client.get("/api/me", headers=auth).json()
    r = client.post(f"/api/admin/users/{me['id']}/revoke", headers=ADMIN)
    assert r.status_code == 200


FOOD_AI = {"is_food": True, "items": [
    {"name": "米饭", "candidates": ["糙米饭"], "grams": 150, "count": 1, "unit": "碗"},
    {"name": "可乐鸡翅", "candidates": [], "grams": 140, "count": 4, "unit": "只"},
    {"name": "清炒上海青", "candidates": [], "grams": 200},
    {"name": "神秘小菜", "grams": 50, "category": "veg", "per100g": {"kcal": 80, "carb": 6, "protein": 2, "fat": 5}},
]}


def test_login_gives_trial_pro(client):
    auth = login(client, "bob")
    me = client.get("/api/me", headers=auth).json()
    assert me["tier"] == "pro"
    assert me["member_id"].startswith("QN")


def test_food_photo_flow_with_fallback_model(client, auth, fake_ai):
    responses, calls = fake_ai
    responses["openai"] = AIError("timeout")
    responses["qwen"] = FOOD_AI
    up = upload(client, auth)
    r = client.post("/api/meals/recognize", headers=auth, json={"upload_id": up["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert calls == ["openai", "qwen"] and d["provider"] == "qwen"
    names = [i["name"] for i in d["items"]]
    assert names[:3] == ["米饭", "鸡翅", "清炒上海青"]
    assert d["items"][2]["food_id"] is not None  # 按别名“上海青”匹配到“炒青菜”的营养数据
    assert d["items"][1]["display"] == "4 只鸡翅"
    assert d["items"][3]["estimated"] is True
    assert "碗饭" in d["summary"]["text"]

    payload = {"meal_type": "lunch", "source": "photo", "photo_upload_id": up["id"],
               "items": [{"food_id": i["food_id"], "name": i["name"], "grams": i["grams"], "category": i["category"], "per100g": i.get("per100g")} for i in d["items"]]}
    r = client.post("/api/meals", headers=auth, json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["cheer"]

    today = client.get("/api/today", headers=auth).json()
    lunch = next(p for p in today["petals"] if p["key"] == "lunch")
    assert lunch["lit"] is True and today["petals_lit"] == 1
    assert today["food"]["text"].startswith("1 碗饭")


def test_ai_all_fail_falls_back_to_search_and_refunds_quota(client, auth, fake_ai):
    responses, _ = fake_ai
    responses["openai"] = AIError("x")
    responses["qwen"] = AIError("y")
    up = upload(client, auth)
    d = client.post("/api/meals/recognize", headers=auth, json={"upload_id": up["id"]}).json()
    assert d["fallback"] == "search"
    q = next(x for x in client.get("/api/me", headers=auth).json()["quotas"] if x["feature"] == "food")
    assert q["used"] == 0


def test_free_quota_runs_out_after_three(client, auth, fake_ai):
    responses, _ = fake_ai
    responses["openai"] = FOOD_AI
    downgrade_to_free(client, auth)
    up = upload(client, auth)
    for _ in range(3):
        assert "items" in client.post("/api/meals/recognize", headers=auth, json={"upload_id": up["id"]}).json()
    d = client.post("/api/meals/recognize", headers=auth, json={"upload_id": up["id"]}).json()
    assert d["fallback"] == "search" and d["reason"] == "quota"


def test_challenge_lights_meals(client, auth):
    client.post("/api/challenges", headers=auth, json={"plan_code": "low_carb", "trial": True})
    rice = client.get("/api/foods/search", headers=auth, params={"q": "米饭"}).json()[0]
    egg = client.get("/api/foods/search", headers=auth, params={"q": "鸡蛋"}).json()[0]
    r1 = client.post("/api/meals", headers=auth, json={"meal_type": "breakfast", "items": [{"food_id": egg["id"], "name": "鸡蛋", "count": 2}, {"name": "炒青菜", "grams": 200}]}).json()
    r2 = client.post("/api/meals", headers=auth, json={"meal_type": "lunch", "items": [{"food_id": rice["id"], "name": "米饭", "count": 2}]}).json()
    assert r1["score"]["lit"] is True
    assert r2["score"]["lit"] is False and r2["score"]["tip"]
    today = client.get("/api/today", headers=auth).json()
    assert today["challenge"]["is_trial"] and today["challenge_today"]["lit_meals"] == 1


def test_copy_meal_and_water(client, auth):
    m = client.post("/api/meals", headers=auth, json={"meal_type": "breakfast", "items": [{"name": "豆浆", "count": 1, "unit": "杯"}]}).json()
    r = client.post(f"/api/meals/{m['id']}/copy", headers=auth, json={"meal_type": "breakfast", "date": str(clock.today() + timedelta(days=1))})
    assert r.status_code == 200
    assert client.post("/api/water", headers=auth, json={"delta": 1}).json()["cups"] == 1


INBODY_AI = {"is_report": True, "model": "InBody570", "fields": {
    "weight_kg": {"value": 70.0, "confidence": 0.95}, "height_cm": {"value": 175, "confidence": 0.9},
    "bmi": {"value": 22.9, "confidence": 0.9}, "body_fat_kg": {"value": 14.0, "confidence": 0.9},
    "fat_free_mass_kg": {"value": 56.0, "confidence": 0.9}, "body_fat_pct": {"value": 20.0, "confidence": 0.9},
    "skeletal_muscle_kg": {"value": 31.5, "confidence": 0.6},
}}


def test_inbody_needs_consent_then_reads(client, auth, fake_ai):
    responses, _ = fake_ai
    responses["openai"] = INBODY_AI
    up = upload(client, auth, "inbody")
    assert client.post("/api/body/recognize", headers=auth, json={"upload_id": up["id"]}).status_code == 428
    client.post("/api/me/consent", headers=auth, json={"kind": "health"})
    d = client.post("/api/body/recognize", headers=auth, json={"upload_id": up["id"]}).json()
    assert d["fields"]["weight_kg"] == 70.0
    assert d["low_confidence"] == ["skeletal_muscle_kg"]
    body = {k: v for k, v in d["fields"].items() if k not in ("measured_at", "height_cm")}
    r = client.post("/api/body", headers=auth, json={**body, "source": "inbody", "image_upload_id": up["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["fields"]["bmi"]["level"] == "normal"
    # 体重差 10 kg 以上要二次确认
    assert client.post("/api/body", headers=auth, json={"weight_kg": 85, "source": "weight"}).status_code == 409
    assert client.post("/api/body", headers=auth, json={"weight_kg": 85, "source": "weight", "confirm_big_change": True}).status_code == 200


def test_inbody_inconsistent_numbers_switch_model(client, auth, fake_ai):
    responses, calls = fake_ai
    bad = {"is_report": True, "fields": {"weight_kg": 70, "height_cm": 175, "bmi": 30, "body_fat_kg": 30,
                                          "fat_free_mass_kg": 56, "body_fat_pct": 10}}
    responses["openai"] = bad
    responses["qwen"] = INBODY_AI
    client.post("/api/me/consent", headers=auth, json={"kind": "health"})
    up = upload(client, auth, "inbody")
    d = client.post("/api/body/recognize", headers=auth, json={"upload_id": up["id"]}).json()
    assert calls == ["openai", "qwen"] and d["provider"] == "qwen"


def test_routine_cycle(client, auth):
    start = clock.today() - timedelta(days=27)
    r = client.post("/api/routines", headers=auth, json={"name": "理发", "icon": "✂️", "cycle_days": 28, "last_done_date": str(start)}).json()
    assert r["days_left"] == 1 and r["state"] == "soon"
    r = client.post(f"/api/routines/{r['id']}/done", headers=auth, json={"note": "短一点"}).json()
    assert r["days_left"] == 28
    detail = client.get(f"/api/routines/{r['id']}", headers=auth).json()
    assert len(detail["logs"]) == 1
    today = client.get("/api/today", headers=auth).json()
    assert next(p for p in today["petals"] if p["key"] == "care")["lit"]


def test_free_routine_limit(client, auth):
    downgrade_to_free(client, auth)
    for i in range(3):
        assert client.post("/api/routines", headers=auth, json={"name": f"事{i}", "cycle_days": 7}).status_code == 200
    assert client.post("/api/routines", headers=auth, json={"name": "第四件", "cycle_days": 7}).status_code == 402


def test_symptom_flow(client, auth):
    body = {"parts": [{"code": "knee.r.patella"}], "symptoms": ["疼痛"], "severity": 5}
    assert client.post("/api/symptoms", headers=auth, json=body).status_code == 428
    client.post("/api/me/consent", headers=auth, json={"kind": "medical"})
    s = client.post("/api/symptoms", headers=auth, json=body).json()
    assert s["parts"][0]["label"] == "膝盖 · 右膝 · 髌骨"
    last = client.get("/api/symptoms/last-at", headers=auth, params={"code": "knee.r"}).json()
    assert last["symptom_id"] == s["id"] and "上次也是这里" in last["text"]
    client.post("/api/medications", headers=auth, json={"symptom_id": s["id"], "name": "布洛芬缓释胶囊", "dose": "1 粒", "times_per_day": 2, "course_days": 3})
    client.post(f"/api/symptoms/{s['id']}/updates", headers=auth, json={"severity": 3})
    summary = client.get(f"/api/symptoms/{s['id']}/summary", headers=auth).json()
    assert any("布洛芬" in l for l in summary["lines"]) and "不替代医生诊断" in summary["disclaimer"]
    healed = client.post(f"/api/symptoms/{s['id']}/heal", headers=auth).json()
    assert healed["status"] == "healed"
    cal = client.get("/api/calendar", headers=auth).json()
    assert cal["days"][str(clock.today())]["sick"] is True
    assert client.post("/api/symptoms", headers=auth, json={**body, "parts": [{"code": "nope"}]}).status_code == 400


def test_redeem_codes(client, auth):
    assert client.post("/api/admin/codes", json={"tier": "pro", "days": 30, "count": 2}).status_code == 403
    codes = client.post("/api/admin/codes", headers=ADMIN, json={"tier": "pro", "days": 30, "count": 2, "batch": "t"}).json()["codes"]
    before = client.get("/api/membership", headers=auth).json()["days_left"]
    r = client.post("/api/membership/redeem", headers=auth, json={"code": codes[0].lower()})
    assert r.status_code == 200 and r.json()["days_left"] >= before + 29
    # 同一个人重复提交：幂等，不重复加
    again = client.post("/api/membership/redeem", headers=auth, json={"code": codes[0]}).json()
    assert again["days_left"] == r.json()["days_left"]
    other = login(client, "carol")
    assert client.post("/api/membership/redeem", headers=other, json={"code": codes[0]}).status_code == 400
    assert client.post("/api/membership/redeem", headers=other, json={"code": "WRONGCODE"}).status_code == 400


def test_upgrade_converts_remaining_days(client, auth):
    me = client.get("/api/me", headers=auth).json()
    client.post(f"/api/admin/users/{me['id']}/revoke", headers=ADMIN)
    client.post(f"/api/admin/users/{me['id']}/grant", headers=ADMIN, json={"tier": "pro", "days": 38})
    code = client.post("/api/admin/codes", headers=ADMIN, json={"tier": "max", "days": 30, "count": 1}).json()["codes"][0]
    d = client.post("/api/membership/redeem", headers=auth, json={"code": code}).json()
    assert d["tier"] == "max" and 47 <= d["days_left"] <= 48  # 38 天 Pro ≈ 18 天 Max，再加 30


def test_trends_and_export(client, auth):
    client.post("/api/me/consent", headers=auth, json={"kind": "health"})
    client.post("/api/body", headers=auth, json={"weight_kg": 70, "source": "weight", "measured_at": (clock.now() - timedelta(days=3)).isoformat()})
    client.post("/api/body", headers=auth, json={"weight_kg": 69, "source": "weight"})
    t = client.get("/api/trends", headers=auth, params={"metric": "weight_kg", "range": "month"}).json()
    assert len(t["points"]) == 2 and "−1" in t["summary"]
    assert client.get("/api/me/export", headers=auth).status_code == 200
    downgrade_to_free(client, auth)
    assert client.get("/api/me/export", headers=auth).status_code == 402
    t = client.get("/api/trends", headers=auth, params={"metric": "weight_kg", "range": "year"}).json()
    assert t["limited_to_90_days"] is True


def test_badges_and_meta(client, auth):
    assert client.get("/api/meta").json()["petals"][0]["key"] == "breakfast"
    b = client.get("/api/me/badges", headers=auth).json()
    assert all(not x["got"] for x in b)


def test_other_users_cannot_touch_my_records(client, auth):
    m = client.post("/api/meals", headers=auth, json={"meal_type": "lunch", "items": [{"name": "米饭", "count": 1}]}).json()
    other = login(client, "mallory")
    assert client.get(f"/api/meals/{m['id']}", headers=other).status_code == 404
    up = upload(client, auth)
    assert client.post("/api/meals/recognize", headers=other, json={"upload_id": up["id"]}).status_code == 404


def test_local_file_link_is_signed(client, auth):
    up = upload(client, auth)
    path = up["url"].replace("http://localhost:8000", "")
    assert client.get(path).status_code == 200
    assert client.get(path.split("?")[0] + "?exp=9999999999&sig=bad").status_code == 403


def test_delete_account(client, auth):
    client.post("/api/meals", headers=auth, json={"meal_type": "lunch", "items": [{"name": "米饭", "count": 1}]})
    assert client.delete("/api/me", headers=auth).status_code == 200
    assert client.get("/api/me", headers=auth).status_code == 401


def test_review_fixes(client, auth):
    # 注销后兑换码不能被别人再用；注销会级联删记录
    code = client.post("/api/admin/codes", headers=ADMIN, json={"tier": "pro", "days": 30, "count": 1}).json()["codes"][0]
    client.post("/api/membership/redeem", headers=auth, json={"code": code})
    client.post("/api/meals", headers=auth, json={"meal_type": "lunch", "items": [{"name": "米饭", "count": 1}]})
    client.delete("/api/me", headers=auth)
    from app.db import SessionLocal
    from app.models import MealLog
    with SessionLocal() as db:
        assert db.query(MealLog).count() == 0
    other = login(client, "dave")
    assert client.post("/api/membership/redeem", headers=other, json={"code": code}).status_code == 400
    # 头像存引用，返回新签名链接
    up = upload(client, other, "avatar")
    me = client.patch("/api/me", headers=other, json={"avatar_upload_id": up["id"]}).json()
    assert "/api/files/" in me["avatar_url"] and "sig=" in me["avatar_url"]


def test_unverified_food_not_matched(client, auth):
    client.post("/api/meals", headers=auth, json={"meal_type": "lunch", "items": [
        {"name": "神秘小菜", "grams": 100, "category": "veg", "per100g": {"kcal": 999, "carb": 1, "protein": 1, "fat": 1}}]})
    d = client.post("/api/meals/preview", headers=auth, json={"items": [{"name": "神秘小菜", "grams": 100, "category": "veg"}]}).json()
    assert d["items"][0]["estimated"] is True and d["items"][0]["kcal"] < 999


def test_expired_challenge_stops_scoring(client, auth):
    from app.db import SessionLocal
    from app.models import Challenge
    c = client.post("/api/challenges", headers=auth, json={"plan_code": "keto", "trial": True}).json()
    with SessionLocal() as db:
        ch = db.get(Challenge, c["id"])
        ch.start_date = clock.today() - timedelta(days=5)
        db.commit()
    assert client.get("/api/today", headers=auth).json()["challenge"] is None


def test_openai_only_via_relay(monkeypatch):
    from app.config import get_settings
    from app.services.ai.client import vision_providers

    assert vision_providers()[0].base_url == "https://relay.test/v1"
    monkeypatch.setattr(get_settings(), "openai_base_url", "")
    assert [p.name for p in vision_providers()] == ["qwen"]


def test_every_ai_endpoint_checks_tier_and_quota(client, auth, fake_ai):
    """所有调用大模型的接口都在后台过鉴权 + 等级 + 配额。"""
    responses, calls = fake_ai
    responses["deepseek"] = {"items": [{"name": "牛肉面", "grams": 500, "count": 1, "unit": "碗"}]}
    responses["openai"] = INBODY_AI
    # 没登录一律 401
    assert client.post("/api/meals/parse-text", json={"text": "一碗牛肉面"}).status_code == 401
    # Pro（试用）可以解读，有每日上限
    client.post("/api/me/consent", headers=auth, json={"kind": "health"})
    rid = client.post("/api/body", headers=auth, json={"weight_kg": 70, "source": "weight"}).json()["id"]
    responses["deepseek"] = {"summary": "保持得不错", "next_steps": ["多走走"]}
    for _ in range(quota.limit_for("interpret", "pro")):
        assert client.post(f"/api/body/{rid}/interpret", headers=auth).status_code == 200
    n = len(calls)
    assert client.post(f"/api/body/{rid}/interpret", headers=auth).status_code == 429
    assert len(calls) == n  # 超额不会再打到模型
    # Free：没有 AI 解读，文字记餐每天 10 次
    downgrade_to_free(client, auth)
    assert client.post(f"/api/body/{rid}/interpret", headers=auth).status_code == 402
    assert "interpret" not in [q["feature"] for q in client.get("/api/me", headers=auth).json()["quotas"]]
    responses["deepseek"] = {"items": [{"name": "牛肉面", "grams": 500, "count": 1, "unit": "碗"}]}
    for _ in range(10):
        assert "items" in client.post("/api/meals/parse-text", headers=auth, json={"text": "一碗牛肉面"}).json()
    d = client.post("/api/meals/parse-text", headers=auth, json={"text": "一碗牛肉面"}).json()
    assert d["fallback"] == "search" and d["reason"] == "quota"


def test_unlimited_tier_still_has_hard_cap():
    from datetime import date

    for _ in range(quota.HARD_CAP["day"]):
        assert quota.try_consume("food", 1, "max", date(2026, 1, 1))
    assert not quota.try_consume("food", 1, "max", date(2026, 1, 1))


def test_reasoning_models_skip_temperature(monkeypatch):
    """GPT-5 以后的推理模型不接受 temperature，只传 reasoning_effort；老模型留空时照旧传 temperature。"""
    import httpx

    from app.services.ai.client import Provider, chat_json

    bodies = []

    def fake_post(url, headers, json, timeout):
        bodies.append(json)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    chat_json(Provider("openai", "https://relay.test/v1", "k", "gpt-6.1-terra", True, "low"), "s", "u")
    chat_json(Provider("openai", "https://relay.test/v1", "k", "gpt-4.1", True), "s", "u")
    assert bodies[0]["reasoning_effort"] == "low" and "temperature" not in bodies[0]
    assert bodies[1]["temperature"] == 0.1 and "reasoning_effort" not in bodies[1]
