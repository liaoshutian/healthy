"""后台任务：发规律生活和服药的订阅消息提醒。在 docker compose 里作为单独的 worker 容器常驻运行。

微信一次性订阅消息：用户每点一次“允许”，我们才能发一条。所以每个事项都有 reminder_credits，发一条扣一次。
"""
import logging
import time
from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import MedicationLog, Routine, User
from app.services import clock
from app.services.routines import next_due
from app.services.wechat import WechatError, send_subscribe_message

log = logging.getLogger("worker")
SEND_HOURS = range(9, 21)  # 只在白天发


def reminder_data(day, note: str) -> dict[str, str]:
    """“日程提醒”模板（健康管理类目，编号 5666）：date2=日程时间，thing3=日程描述（最多 20 字）。规律小事和吃药提醒共用。"""
    return {"date2": f"{day.year}年{day.month}月{day.day}日 09:00", "thing3": note[:20]}


def routine_reminders(db) -> int:
    s = get_settings()
    if not s.wx_tmpl_routine:
        return 0
    today = clock.today()
    sent = 0
    rows = db.execute(select(Routine, User).join(User).where(Routine.archived.is_(False), Routine.reminder_credits > 0))
    for r, u in rows:
        due = next_due(r, today)
        if today < due - timedelta(days=r.remind_days_before) or r.last_reminded_for == due:
            continue
        days_left = (due - today).days
        tip = "今天就是计划的日子" if days_left == 0 else (f"还有 {days_left} 天" if days_left > 0 else "已经到时间啦")
        ok = send_subscribe_message(u.openid, s.wx_tmpl_routine, f"pages/routine/index?id={r.id}",
                                    reminder_data(due, f"{r.name}：{tip}"))
        r.last_reminded_for = due
        r.reminder_credits = max(0, r.reminder_credits - 1)
        sent += int(ok)
    db.commit()
    return sent


def medication_reminders(db) -> int:
    s = get_settings()
    if not s.wx_tmpl_routine:
        return 0
    today = clock.today()
    sent = 0
    rows = db.execute(select(MedicationLog, User).join(User).where(MedicationLog.remind.is_(True), MedicationLog.reminder_credits > 0))
    for m, u in rows:
        end = m.start_date + timedelta(days=(m.course_days or 1) - 1)
        if not (m.start_date <= today <= end):
            continue
        # 每天只在 9 点那一轮发一条
        if clock.now().hour != 9:
            continue
        dose = f" 每次{m.dose}" if m.dose else ""
        ok = send_subscribe_message(u.openid, s.wx_tmpl_routine, "pages/record/index",
                                    reminder_data(today, f"吃药：{m.name}{dose}"))
        m.reminder_credits = max(0, m.reminder_credits - 1)
        sent += int(ok)
    db.commit()
    return sent


def run_once() -> None:
    if clock.now().hour not in SEND_HOURS:
        return
    with SessionLocal() as db:
        try:
            n1 = routine_reminders(db)
            n2 = medication_reminders(db)
            if n1 or n2:
                log.info("提醒已发送：规律 %d 条，服药 %d 条", n1, n2)
        except WechatError as e:
            log.warning("微信接口出错：%s", e)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("worker started")
    last_hour = None
    while True:
        h = clock.now().replace(minute=0, second=0, microsecond=0)
        if h != last_hour:  # 每小时跑一轮
            run_once()
            last_hour = h
        time.sleep(60)


if __name__ == "__main__":
    main()
