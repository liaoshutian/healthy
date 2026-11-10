from datetime import date, timedelta

from app.models import Routine


def next_due(r: Routine, today: date) -> date:
    base = r.last_done_date or r.created_at.date()
    due = base + timedelta(days=r.cycle_days)
    if r.snooze_until and r.snooze_until > due:
        due = r.snooze_until
    return due


def status(r: Routine, today: date) -> dict:
    due = next_due(r, today)
    days_left = (due - today).days
    since = (today - r.last_done_date).days if r.last_done_date else None
    if days_left < 0:
        state, text = "overdue", f"该{r.name}啦，比计划晚了 {-days_left} 天"
    elif days_left == 0:
        state, text = "due", f"今天{r.name}"
    elif days_left <= max(r.remind_days_before, 7):
        state, text = "soon", f"还有 {days_left} 天"
    else:
        state, text = "ok", f"还有 {days_left} 天"
    progress = min(1.0, (since or 0) / r.cycle_days) if r.cycle_days else 0
    return {"due_date": due, "days_left": days_left, "days_since": since, "state": state, "text": text, "progress": round(progress, 2)}


def average_cycle(done_dates: list[date]) -> float | None:
    ds = sorted(done_dates)
    if len(ds) < 2:
        return None
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    return round(sum(gaps) / len(gaps), 1)
