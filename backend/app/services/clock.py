from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    return datetime.now(TZ)


def today() -> date:
    return now().date()


def local(dt: datetime) -> datetime:
    """数据库读出的时间（UTC）转北京时间。"""
    return dt.astimezone(TZ)
