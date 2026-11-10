"""今日概览、青柠果瓣、温和的连续记录、徽章、日历、趋势。"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BodyRecord,
    Challenge,
    MealLog,
    MedicalRecord,
    MedicationLog,
    Routine,
    RoutineLog,
    SymptomLog,
    SymptomUpdate,
    User,
    WaterLog,
)
from app.services import clock, plans, portions

PETALS = [
    ("breakfast", "早餐", "🍳"),
    ("lunch", "午餐", "🍱"),
    ("dinner", "晚餐", "🍲"),
    ("water", "喝水", "💧"),
    ("body", "称一称", "⚖️"),
    ("care", "照顾自己", "🌱"),  # 完成一件规律事，或记一次身体状况
]
MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=clock.TZ)
    return start, start + timedelta(days=1)


def item_dict(i) -> dict:
    return {"name": i.name, "category": i.category, "grams": i.grams, "kcal": i.kcal, "carb": i.carb,
            "protein": i.protein, "fat": i.fat, "tags": i.tags or []}


def active_challenge(db: Session, user: User) -> Challenge | None:
    """进行中的挑战；到期的顺手标成完成，不再参与打分。"""
    today = clock.today()
    for c in db.scalars(select(Challenge).where(Challenge.user_id == user.id, Challenge.status == "active").order_by(Challenge.id.desc())):
        if (today - c.start_date).days >= c.days:
            c.status, c.ended_at = "done", clock.now()
            db.commit()
            continue
        return c
    return None


def challenge_public(c: Challenge | None, today: date) -> dict | None:
    if not c:
        return None
    plan = plans.PLANS[c.plan_code]
    day_n = (today - c.start_date).days + 1
    return {"id": c.id, "plan": plans.plan_public(plan), "days": c.days, "day_n": min(day_n, c.days),
            "status": c.status, "start_date": c.start_date, "is_trial": c.days == 3}


def day_flags(db: Session, user: User, d: date) -> dict:
    """某一天每类记录有没有，用于果瓣。"""
    start, end = _day_bounds(d)
    meal_types = set(db.scalars(select(MealLog.meal_type).where(MealLog.user_id == user.id, MealLog.date == d)))
    water = db.scalar(select(WaterLog.cups).where(WaterLog.user_id == user.id, WaterLog.date == d)) or 0
    body = db.scalar(select(func.count(BodyRecord.id)).where(
        BodyRecord.user_id == user.id, BodyRecord.measured_at >= start, BodyRecord.measured_at < end)) or 0
    routine = db.scalar(select(func.count(RoutineLog.id)).where(RoutineLog.user_id == user.id, RoutineLog.done_date == d)) or 0
    symptom_upd = db.scalar(select(func.count(SymptomUpdate.id)).join(SymptomLog).where(
        SymptomLog.user_id == user.id, SymptomUpdate.date == d)) or 0
    return {
        "breakfast": "breakfast" in meal_types,
        "lunch": "lunch" in meal_types,
        "dinner": "dinner" in meal_types,
        "water": water > 0,
        "body": body > 0,
        "care": routine > 0 or symptom_upd > 0,
        "_snack": "snack" in meal_types,
        "_water_cups": water,
    }


def record_dates(db: Session, user: User, since: date) -> set[date]:
    """有任意记录的日期集合。"""
    days: set[date] = set()
    days.update(db.scalars(select(MealLog.date).where(MealLog.user_id == user.id, MealLog.date >= since)))
    days.update(db.scalars(select(WaterLog.date).where(WaterLog.user_id == user.id, WaterLog.date >= since, WaterLog.cups > 0)))
    days.update(db.scalars(select(RoutineLog.done_date).where(RoutineLog.user_id == user.id, RoutineLog.done_date >= since)))
    start, _ = _day_bounds(since)
    for dt in db.scalars(select(BodyRecord.measured_at).where(BodyRecord.user_id == user.id, BodyRecord.measured_at >= start)):
        days.add(dt.astimezone(clock.TZ).date() if dt.tzinfo else dt.date())
    days.update(db.scalars(select(SymptomUpdate.date).join(SymptomLog).where(
        SymptomLog.user_id == user.id, SymptomUpdate.date >= since)))
    return days


def gentle_streak(days: set[date], today: date) -> dict:
    """断签不清零：每周自动送 1 张休息卡补签。今天还没记不算断。"""
    streak, used_weeks = 0, set()
    d = today if today in days else today - timedelta(days=1)
    rest_used = 0
    for _ in range(800):
        if d in days:
            streak += 1
        else:
            week = d.isocalendar()[:2]
            if week in used_weeks:
                break
            used_weeks.add(week)
            rest_used += 1
        d -= timedelta(days=1)
    # 末尾连续用掉的休息卡不算进连续天数
    month_days = sum(1 for x in days if x.year == today.year and x.month == today.month)
    return {"streak_days": streak, "rest_cards_used": rest_used, "month_days": month_days}


def today_overview(db: Session, user: User) -> dict:
    today = clock.today()
    flags = day_flags(db, user, today)
    petals = [{"key": k, "label": label, "icon": icon, "lit": flags[k]} for k, label, icon in PETALS]
    lit_count = sum(p["lit"] for p in petals)

    meals = list(db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.date == today).order_by(MealLog.id)))
    all_items = [item_dict(i) for m in meals for i in m.items]
    by_type = {t: [] for t in MEAL_TYPES}
    for m in meals:
        by_type[m.meal_type].append(meal_brief(m))
    challenge = active_challenge(db, user)
    lit_meals = sum(1 for m in meals if m.plan_lit)

    routines = list(db.scalars(select(Routine).where(Routine.user_id == user.id, Routine.archived.is_(False))))
    from app.services.routines import status as rstatus

    upcoming = []
    for r in routines:
        st = rstatus(r, today)
        if st["days_left"] <= 7:
            upcoming.append({"id": r.id, "name": r.name, "icon": r.icon, **st})
    upcoming.sort(key=lambda x: x["days_left"])

    active_symptoms = list(db.scalars(select(SymptomLog).where(SymptomLog.user_id == user.id, SymptomLog.status == "active")))
    days = record_dates(db, user, today - timedelta(days=400))

    return {
        "date": today,
        "petals": petals,
        "petals_lit": lit_count,
        "petals_total": len(petals),
        "complete": lit_count == len(petals),
        "water_cups": flags["_water_cups"],
        "food": {
            **portions.summarize(all_items),
            "kcal": round(sum(i["kcal"] for i in all_items)),
            "carb": round(sum(i["carb"] for i in all_items)),
            "protein": round(sum(i["protein"] for i in all_items)),
            "fat": round(sum(i["fat"] for i in all_items)),
        },
        "meals": [{"type": t, "label": MEAL_LABELS[t], "logs": by_type[t]} for t in MEAL_TYPES],
        "challenge": challenge_public(challenge, today),
        "challenge_today": {"lit_meals": lit_meals, "goal": plans.DAY_GOAL_LIT_MEALS,
                             "done": lit_meals >= plans.DAY_GOAL_LIT_MEALS} if challenge else None,
        "routines": upcoming,
        "body": body_snapshot(db, user, today),
        "symptoms": [{"id": s.id, "parts": s.parts, "symptoms": s.symptoms, "severity": s.severity,
                      "title": "、".join(p["label"].split(" · ")[-1] for p in s.parts) + (" · " + "、".join(s.symptoms) if s.symptoms else ""),
                      "checked_today": any(u.date == today for u in s.updates)} for s in active_symptoms],
        "streak": gentle_streak(days, today),
    }


def meal_brief(m: MealLog) -> dict:
    items = [item_dict(i) for i in m.items]
    return {"id": m.id, "meal_type": m.meal_type, "kcal": round(m.kcal), "photo_upload_id": m.photo_upload_id,
            "names": [i.name for i in m.items], "title": "、".join(i.name for i in m.items), "summary": portions.summarize(items)["text"],
            "plan_lit": m.plan_lit, "plan_code": m.plan_code, "plan_tip": m.plan_tip}


def body_snapshot(db: Session, user: User, today: date) -> dict | None:
    recs = list(db.scalars(select(BodyRecord).where(BodyRecord.user_id == user.id).order_by(BodyRecord.measured_at.desc()).limit(2)))
    if not recs:
        return None
    cur, prev = recs[0], recs[1] if len(recs) > 1 else None

    def delta(attr):
        a, b = getattr(cur, attr), getattr(prev, attr) if prev else None
        return round(a - b, 1) if a is not None and b is not None else None

    last_inbody = db.scalar(select(func.max(BodyRecord.measured_at)).where(BodyRecord.user_id == user.id, BodyRecord.source == "inbody"))
    start, _ = _day_bounds(today - timedelta(days=30))
    series = list(db.execute(select(BodyRecord.measured_at, BodyRecord.weight_kg).where(
        BodyRecord.user_id == user.id, BodyRecord.measured_at >= start, BodyRecord.weight_kg.is_not(None)
    ).order_by(BodyRecord.measured_at)))
    stale = True
    if last_inbody:
        li = last_inbody if last_inbody.tzinfo else last_inbody.replace(tzinfo=clock.TZ)
        stale = (clock.now() - li).days > 30
    return {
        "measured_at": cur.measured_at,
        "weight_kg": cur.weight_kg, "body_fat_pct": cur.body_fat_pct, "skeletal_muscle_kg": cur.skeletal_muscle_kg,
        "delta": {"weight_kg": delta("weight_kg"), "body_fat_pct": delta("body_fat_pct"), "skeletal_muscle_kg": delta("skeletal_muscle_kg")},
        "mini_series": [w for _, w in series],
        "inbody_hint": "好久没测体成分了，有空去测一次吧" if stale else None,
    }


# ---------- 徽章 ----------

BADGES = [
    ("first_inbody", "第一张报告", "📄", "第一次拍 InBody 报告"),
    ("first_photo_meal", "咔嚓一下", "📸", "第一次拍照记饭"),
    ("days_7", "七天小柠", "🍋", "累计记录 7 天"),
    ("days_30", "一个月啦", "🌿", "累计记录 30 天"),
    ("days_100", "百日青柠", "🌳", "累计记录 100 天"),
    ("full_lime", "完整的一天", "🟢", "有一天点满整片青柠"),
    ("routine_12", "准时达人", "⏰", "规律事项按时完成 12 次"),
    ("challenge_21", "挑战完成", "🏅", "完成一张 21 天挑战卡"),
    ("healed", "好起来了", "💪", "记下一次痊愈"),
]


def badges(db: Session, user: User) -> list[dict]:
    days = record_dates(db, user, date(2000, 1, 1))
    got = set()
    if db.scalar(select(func.count(BodyRecord.id)).where(BodyRecord.user_id == user.id, BodyRecord.source == "inbody")):
        got.add("first_inbody")
    if db.scalar(select(func.count(MealLog.id)).where(MealLog.user_id == user.id, MealLog.source == "photo")):
        got.add("first_photo_meal")
    for n in (7, 30, 100):
        if len(days) >= n:
            got.add(f"days_{n}")
    for d in sorted(days, reverse=True)[:60]:
        f = day_flags(db, user, d)
        if all(f[k] for k, *_ in PETALS):
            got.add("full_lime")
            break
    ontime = 0
    for r in db.scalars(select(Routine).where(Routine.user_id == user.id)):
        ds = sorted(l.done_date for l in r.logs)
        ontime += sum(1 for a, b in zip(ds, ds[1:]) if (b - a).days <= r.cycle_days + 2)
    if ontime >= 12:
        got.add("routine_12")
    if db.scalar(select(func.count(Challenge.id)).where(Challenge.user_id == user.id, Challenge.status == "done", Challenge.days >= 21)):
        got.add("challenge_21")
    if db.scalar(select(func.count(SymptomLog.id)).where(SymptomLog.user_id == user.id, SymptomLog.status == "healed")):
        got.add("healed")
    return [{"code": c, "name": n, "icon": i, "desc": d, "got": c in got} for c, n, i, d in BADGES]


# ---------- 日历 ----------

def calendar_month(db: Session, user: User, year: int, month: int) -> dict:
    first = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    start, _ = _day_bounds(first)
    end, _ = _day_bounds(nxt)
    days: dict[date, dict] = defaultdict(lambda: {"meals": 0, "lit_meals": 0, "kcal": 0, "body": False,
                                                  "routines": [], "sick": False, "water": 0})
    for m in db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.date >= first, MealLog.date < nxt)):
        d = days[m.date]
        d["meals"] += 1
        d["lit_meals"] += int(m.plan_lit)
        d["kcal"] += round(m.kcal)
    for w in db.scalars(select(WaterLog).where(WaterLog.user_id == user.id, WaterLog.date >= first, WaterLog.date < nxt)):
        days[w.date]["water"] = w.cups
    for dt in db.scalars(select(BodyRecord.measured_at).where(BodyRecord.user_id == user.id, BodyRecord.measured_at >= start, BodyRecord.measured_at < end)):
        days[(dt.astimezone(clock.TZ) if dt.tzinfo else dt).date()]["body"] = True
    for log, r in db.execute(select(RoutineLog, Routine).join(Routine).where(
            RoutineLog.user_id == user.id, RoutineLog.done_date >= first, RoutineLog.done_date < nxt)):
        days[log.done_date]["routines"].append({"name": r.name, "icon": r.icon})
    today = clock.today()
    for s in db.scalars(select(SymptomLog).where(SymptomLog.user_id == user.id)):
        s_start = (s.started_at.astimezone(clock.TZ) if s.started_at.tzinfo else s.started_at).date()
        s_end = (s.healed_at.astimezone(clock.TZ) if s.healed_at and s.healed_at.tzinfo else s.healed_at).date() if s.healed_at else today
        d = max(s_start, first)
        while d < nxt and d <= s_end:
            days[d]["sick"] = True
            d += timedelta(days=1)
    for med in db.scalars(select(MedicationLog).where(MedicationLog.user_id == user.id)):
        d_end = med.start_date + timedelta(days=(med.course_days or 1) - 1)
        d = max(med.start_date, first)
        while d < nxt and d <= d_end:
            days[d]["sick"] = True
            d += timedelta(days=1)
    for r in db.scalars(select(MedicalRecord).where(MedicalRecord.user_id == user.id, MedicalRecord.visit_date >= first, MedicalRecord.visit_date < nxt)):
        days[r.visit_date]["sick"] = True
    return {"year": year, "month": month, "days": {d.isoformat(): v for d, v in sorted(days.items())}}


def day_detail(db: Session, user: User, d: date) -> dict:
    start, end = _day_bounds(d)
    meals = list(db.scalars(select(MealLog).where(MealLog.user_id == user.id, MealLog.date == d).order_by(MealLog.id)))
    items = [item_dict(i) for m in meals for i in m.items]
    return {
        "date": d,
        "food": portions.summarize(items),
        "meals": [meal_brief(m) for m in meals],
        "water": db.scalar(select(WaterLog.cups).where(WaterLog.user_id == user.id, WaterLog.date == d)) or 0,
        "body": [{"id": b.id, "source": b.source, "weight_kg": b.weight_kg, "body_fat_pct": b.body_fat_pct}
                 for b in db.scalars(select(BodyRecord).where(BodyRecord.user_id == user.id, BodyRecord.measured_at >= start, BodyRecord.measured_at < end))],
        "routines": [{"name": r.name, "icon": r.icon, "note": l.note} for l, r in db.execute(
            select(RoutineLog, Routine).join(Routine).where(RoutineLog.user_id == user.id, RoutineLog.done_date == d))],
        "symptom_updates": [{"symptom_id": s.id, "severity": u.severity, "note": u.note} for u, s in db.execute(
            select(SymptomUpdate, SymptomLog).join(SymptomLog).where(SymptomLog.user_id == user.id, SymptomUpdate.date == d))],
    }


# ---------- 趋势 ----------

METRICS = {
    "weight_kg": ("体重", "kg"),
    "body_fat_pct": ("体脂率", "%"),
    "skeletal_muscle_kg": ("骨骼肌", "kg"),
    "visceral_fat_level": ("内脏脂肪", "级"),
    "kcal": ("每日热量", "千卡"),
}
RANGES = {"week": 7, "month": 30, "3m": 90, "year": 365, "all": 36500}


def trend(db: Session, user: User, metric: str, rng: str, tier: str) -> dict:
    today = clock.today()
    days = RANGES[rng]
    limited = False
    if tier == "free" and days > 90:
        days, limited = 90, True
    since = today - timedelta(days=days - 1)
    points: list[tuple[date, float]] = []
    if metric == "kcal":
        rows = db.execute(select(MealLog.date, func.sum(MealLog.kcal)).where(
            MealLog.user_id == user.id, MealLog.date >= since).group_by(MealLog.date).order_by(MealLog.date))
        points = [(d, round(v)) for d, v in rows]
    else:
        start, _ = _day_bounds(since)
        col = getattr(BodyRecord, metric)
        rows = db.execute(select(BodyRecord.measured_at, col).where(
            BodyRecord.user_id == user.id, BodyRecord.measured_at >= start, col.is_not(None)).order_by(BodyRecord.measured_at))
        by_day: dict[date, float] = {}
        for dt, v in rows:
            by_day[(dt.astimezone(clock.TZ) if dt.tzinfo else dt).date()] = v  # 同一天取最后一次
        points = sorted(by_day.items())
    ma = []
    for i, (d, _) in enumerate(points):
        window = [v for dd, v in points[: i + 1] if (d - dd).days < 7]
        ma.append(round(sum(window) / len(window), 2))
    label, unit = METRICS[metric]
    summary = None
    if len(points) >= 2:
        diff = points[-1][1] - points[0][1]
        span = (points[-1][0] - points[0][0]).days
        sign = "+" if diff > 0 else ("−" if diff < 0 else "±")
        summary = f"{span} 天 {label} {sign}{abs(round(diff, 1)):g} {unit}"
    return {
        "metric": metric, "label": label, "unit": unit, "range": rng, "limited_to_90_days": limited,
        "points": [{"date": d, "value": v} for d, v in points], "moving_avg_7d": ma, "summary": summary,
    }
