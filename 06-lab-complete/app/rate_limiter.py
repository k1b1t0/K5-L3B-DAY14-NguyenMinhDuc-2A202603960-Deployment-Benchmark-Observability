"""
Rate limiting (tiêu chí 7) — sliding window trong Redis.
"""
import time
import uuid
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    """Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây."""
    if r is None:
        return
    now = time.time()
    window_start = now - 60.0
    redis_key = f"ratelimit:{key}"
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, count = pipe.execute()

        if count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"},
            )

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, 65)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        # Nếu Redis tạm lỗi, không làm sập request hợp lệ
        return
