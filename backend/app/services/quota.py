"""每日/每月 AI 配额计数。key = 功能 + 用户 + 周期，生产用 Redis，开发和测试可用内存。"""
from datetime import date

from app.config import get_settings

# (周期, Free 上限, Pro 上限, Max 上限)；None = 不限
LIMITS: dict[str, tuple[str, int | None, int | None, int | None]] = {
    "food": ("day", 3, 30, None),
    "inbody": ("month", 1, None, None),
    "medicine": ("day", 3, 30, None),
}


class _MemoryCounter:
    def __init__(self):
        self.data: dict[str, int] = {}

    def get(self, key):
        return self.data.get(key)

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def decr(self, key):
        self.data[key] = self.data.get(key, 0) - 1
        return self.data[key]

    def expire(self, key, seconds):
        pass


_client = None


def get_counter():
    global _client
    if _client is None:
        url = get_settings().redis_url
        if url:
            import redis

            _client = redis.Redis.from_url(url, decode_responses=True)
        else:
            _client = _MemoryCounter()
    return _client


def set_counter(client) -> None:
    global _client
    _client = client


def _key(feature: str, user_id: int, today: date) -> tuple[str, int]:
    period = LIMITS[feature][0]
    if period == "day":
        return f"quota:{feature}:{user_id}:{today.isoformat()}", 2 * 86400
    return f"quota:{feature}:{user_id}:{today:%Y-%m}", 40 * 86400


def limit_for(feature: str, tier: str) -> int | None:
    _, free, pro, mx = LIMITS[feature]
    return {"free": free, "pro": pro, "max": mx}[tier]


def usage(feature: str, user_id: int, tier: str, today: date) -> dict:
    key, _ = _key(feature, user_id, today)
    used = int(get_counter().get(key) or 0)
    limit = limit_for(feature, tier)
    return {"feature": feature, "used": used, "limit": limit, "period": LIMITS[feature][0]}


def try_consume(feature: str, user_id: int, tier: str, today: date) -> bool:
    """先占一次额度；超额返回 False。调用失败时用 refund 退回。"""
    key, ttl = _key(feature, user_id, today)
    c = get_counter()
    n = c.incr(key)
    if n == 1:
        c.expire(key, ttl)
    limit = limit_for(feature, tier)
    if limit is not None and n > limit:
        c.decr(key)
        return False
    return True


def refund(feature: str, user_id: int, today: date) -> None:
    key, _ = _key(feature, user_id, today)
    get_counter().decr(key)
