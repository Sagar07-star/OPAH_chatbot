"""In-process rate limiting for chat messages and uploads.

Numbers are configuration (see config.py); the goal is to keep the prototype's
guardrail behaviour identical to production, not to defend a public service.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from ..config import settings


@dataclass
class Decision:
    allowed: bool
    code: str = ""
    message: str = ""
    retry_after: int = 0


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        return bucket

    def check(self, identity: str, kind: str, role: str) -> Decision:
        limits = {
            "message": (settings.rate_anon_per_minute, settings.rate_anon_per_hour)
            if role == "anonymous" else (settings.rate_client_per_minute, settings.rate_client_per_hour),
            "upload": (4, 30) if role == "anonymous" else (30, 300),
        }[kind]
        key = f"{identity}:{kind}"
        now = time.time()
        with self._lock:
            minute = self._prune(key, 60, now)
            hour = self._prune(key + ":h", 3600, now)
            if len(minute) >= limits[0]:
                return Decision(False, "rate_limited",
                                "That's a lot in a minute. Give it a moment before the next message.", 60)
            if len(hour) >= limits[1]:
                return Decision(False, "rate_limited",
                                "You've hit the hourly limit for this prototype. Try again later.", 3600)
            minute.append(now)
            hour.append(now)
        return Decision(True)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
