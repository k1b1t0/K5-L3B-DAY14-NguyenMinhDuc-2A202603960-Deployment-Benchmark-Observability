"""
Cost guard (tiêu chí 8) — theo dõi chi phí LLM trong Redis.
"""
import time
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _daily_key() -> str:
    return f"cost:daily:{time.strftime('%Y-%m-%d')}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    if r is None:
        return
    try:
        raw = r.get(_daily_key())
        used = float(raw) if raw is not None else 0.0
        if used >= settings.daily_budget_usd:
            raise HTTPException(
                status_code=402,
                detail="Daily budget exceeded",
            )
    except HTTPException:
        raise
    except Exception:
        return


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (
        output_tokens / 1000.0
    ) * PRICE_OUTPUT_PER_1K
    if r is not None:
        try:
            key = _daily_key()
            r.incrbyfloat(key, cost)
            r.expire(key, 86400 * 2)
        except Exception:
            pass
    return round(cost, 8)
