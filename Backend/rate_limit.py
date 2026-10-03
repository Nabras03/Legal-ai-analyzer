"""In-memory request limits for the public demo.

Per-IP limits stop casual overuse; the global daily cap is what actually
protects the API quota, since a determined user can change IP address or
forge forwarding headers. State lives in memory, so it resets when the
server restarts (on Render's free plan, after it sleeps), which is fine for a
demo with a single instance.
"""

import time
from collections import deque

from fastapi import Request

MINUTE = 60
DAY = 24 * 60 * 60


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind Render's proxy the TCP peer is the proxy, and
    the original client is the first address in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, global_per_day: int, clock=time.monotonic):
        self.per_minute = per_minute
        self.per_day = per_day
        self.global_per_day = global_per_day
        self.clock = clock
        self._by_ip: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()

    @staticmethod
    def _prune(times: deque[float], now: float) -> None:
        while times and times[0] <= now - DAY:
            times.popleft()

    def check(self, ip: str) -> str | None:
        """Record a request from `ip`, or return why it is refused."""
        now = self.clock()
        self._prune(self._all, now)
        times = self._by_ip.setdefault(ip, deque())
        self._prune(times, now)

        if len(self._all) >= self.global_per_day:
            return "The demo has reached its daily limit. Please try again tomorrow."
        if len(times) >= self.per_day:
            return f"You have reached the limit of {self.per_day} analyses per day. Please try again tomorrow."
        if sum(t > now - MINUTE for t in times) >= self.per_minute:
            return f"Too many requests: at most {self.per_minute} analyses per minute. Wait a moment and try again."

        times.append(now)
        self._all.append(now)
        return None
