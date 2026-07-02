"""Small rate limiter for Groq free-tier limits."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone

from src.config import LLM_LIMITS, LLM_SAFETY
from src.db import get_connection, init_db

logger = logging.getLogger(__name__)

# Minimum gap between API calls to stay under Groq RPM.
MIN_REQUEST_INTERVAL_SEC = 2.5


class DailyLimitReached(RuntimeError):
    """Raised when the daily request/token budget would be exceeded."""


class LLMRateLimiter:
    """Enforces RPM/TPM in memory and RPD/TPD in SQLite."""

    _daily_stopped: bool = False

    def __init__(self) -> None:
        self._events: deque[tuple[float, int]] = deque()
        self._last_request_at: float = 0.0

    @classmethod
    def reset_daily_stop(cls) -> None:
        """Reset the in-process stop flag (mainly for tests)."""
        cls._daily_stopped = False

    @staticmethod
    def estimate_tokens(prompt: str, max_output_tokens: int = 512) -> int:
        # Cheap approximation: ~0.75 words per token in English.  Err high.
        return int(len(prompt.split()) * 1.5) + max_output_tokens

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _minute_limits(self) -> tuple[int, int]:
        rpm = int(LLM_LIMITS["rpm"] * LLM_SAFETY)
        tpm = int(LLM_LIMITS["tpm"] * LLM_SAFETY)
        return rpm, tpm

    def _daily_limits(self) -> tuple[int, int]:
        rpd = int(LLM_LIMITS["rpd"] * LLM_SAFETY)
        tpd = int(LLM_LIMITS["tpd"] * LLM_SAFETY)
        return rpd, tpd

    def get_usage(self) -> tuple[int, int]:
        """Return (requests_used_today, tokens_used_today)."""
        init_db()
        today = self._today_key()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT requests, tokens FROM llm_usage WHERE day = ?",
                (today,),
            ).fetchone()
        if not row:
            return 0, 0
        return int(row["requests"]), int(row["tokens"])

    def is_daily_limit_reached(self, estimated_tokens: int = 0) -> bool:
        """True when today's budget is exhausted or the next call would exceed it."""
        if self.__class__._daily_stopped:
            return True

        requests_used, tokens_used = self.get_usage()
        rpd, tpd = self._daily_limits()
        return (
            requests_used >= rpd
            or tokens_used >= tpd
            or requests_used + 1 > rpd
            or tokens_used + estimated_tokens > tpd
        )

    def mark_daily_stopped(self, reason: str) -> None:
        """Set the in-process flag so all later calls fail fast."""
        self.__class__._daily_stopped = True
        logger.warning("LLM daily budget stop engaged: %s", reason)

    def reserve(self, estimated_tokens: int) -> None:
        """Block for minute limits or raise for daily limits."""
        if self.is_daily_limit_reached(estimated_tokens):
            self.mark_daily_stopped("daily request/token budget reached")
            raise DailyLimitReached("Groq daily LLM limit reached")

        # Pace requests so we do not burst past Groq RPM.
        if self._last_request_at:
            elapsed = time.time() - self._last_request_at
            if elapsed < MIN_REQUEST_INTERVAL_SEC:
                time.sleep(MIN_REQUEST_INTERVAL_SEC - elapsed)

        rpm, tpm = self._minute_limits()
        while True:
            now = time.time()
            while self._events and now - self._events[0][0] >= 60:
                self._events.popleft()

            minute_requests = len(self._events)
            minute_tokens = sum(tokens for _, tokens in self._events)
            if minute_requests + 1 <= rpm and minute_tokens + estimated_tokens <= tpm:
                self._events.append((now, estimated_tokens))
                return

            if not self._events:
                self._events.append((now, estimated_tokens))
                return

            sleep_for = max(1.0, 60 - (now - self._events[0][0]))
            logger.info("LLM rate limiter: waiting %.1fs for minute window", sleep_for)
            time.sleep(min(sleep_for, 15.0))

    def record(self, actual_tokens: int) -> None:
        """Record actual request/token usage for the current day."""
        init_db()
        today = self._today_key()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_usage (day, requests, tokens)
                VALUES (?, 1, ?)
                ON CONFLICT(day) DO UPDATE SET
                    requests = requests + 1,
                    tokens = tokens + excluded.tokens
                """,
                (today, actual_tokens),
            )

        self._last_request_at = time.time()

        if self.is_daily_limit_reached():
            self.mark_daily_stopped("daily budget exhausted after last request")
