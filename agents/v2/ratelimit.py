"""Process-wide request pacing for free-tier LLM APIs.

Free tiers cap requests per minute. Without pacing, a parallel benchmark gets
HTTP 429 errors, which the legacy agents turn into heuristic fallbacks: the
benchmark would then measure the provider's quota, not the agents. Every LLM
call (v2 runner and legacy agents wrapped by the benchmark) goes through one
shared limiter configured by ``LLM_MAX_RPM``.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict


class RateLimiter:
    def __init__(self, max_per_minute: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / max_per_minute if max_per_minute and max_per_minute > 0 else 0.0
        self.clock = clock
        self.sleep = sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a request slot is free; return the time waited."""
        if not self.interval:
            return 0.0
        with self._lock:
            now = self.clock()
            slot = max(now, self._next)
            self._next = slot + self.interval
        wait = slot - now
        if wait > 0:
            self.sleep(wait)
        return wait


_LIMITERS: Dict[str, RateLimiter] = {}
_GLOBAL_LOCK = threading.Lock()


def global_limiter(model_id: str = "") -> RateLimiter:
    """One limiter per model: free tiers apply their quotas per model."""
    with _GLOBAL_LOCK:
        if model_id not in _LIMITERS:
            from config import LLM_MAX_RPM

            _LIMITERS[model_id] = RateLimiter(LLM_MAX_RPM)
        return _LIMITERS[model_id]


def is_rate_limit_error(text: Any) -> bool:
    lowered = str(text).lower()
    return any(marker in lowered for marker in ("429", "rate limit", "rate_limit", "too many requests",
                                                "quota", "capacity exceeded",
                                                # Agno hides provider HTTP errors behind this message
                                                "unknown model error"))


class QuotaExhausted(BaseException):
    """Provider quota exhausted after all retries.

    Derives from BaseException on purpose: agents catch ``Exception`` and would
    otherwise record a heuristic fallback, silently mixing quota failures into
    the quality metrics. The benchmark stops instead and can be resumed.
    """
