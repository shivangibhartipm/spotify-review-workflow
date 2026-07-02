"""Groq LLM client wrapper with cache and rate limiting."""

from __future__ import annotations

import logging
import time

import truststore
from groq import APIConnectionError, APITimeoutError, RateLimitError

from src.config import GROQ_API_KEY, GROQ_MODEL
from src.llm.cache import get_cached, set_cached
from src.llm.rate_limiter import DailyLimitReached, LLMRateLimiter

truststore.inject_into_ssl()

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when the LLM cannot be used, usually due to missing API key."""


class RateLimitStop(RuntimeError):
    """Raised when Groq returns repeated rate-limit errors for this run."""


class GroqLLMClient:
    """Minimal Groq chat-completions wrapper."""

    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise LLMUnavailable("GROQ_API_KEY is not configured")

        from groq import Groq

        self._client = Groq(api_key=GROQ_API_KEY)
        self._limiter = LLMRateLimiter()

    def complete_json(self, prompt: str, max_output_tokens: int = 768) -> str:
        """
        Return raw model content, using cache before hitting the network.

        Stops immediately when the daily budget is exhausted.  Does not retry
        daily-limit failures or repeated Groq 429 responses.
        """
        cached = get_cached(prompt, GROQ_MODEL)
        if cached is not None:
            return cached

        estimate = self._limiter.estimate_tokens(prompt, max_output_tokens)
        if self._limiter.is_daily_limit_reached(estimate):
            self._limiter.mark_daily_stopped("daily budget already exhausted")
            raise DailyLimitReached("Groq daily LLM limit already reached")

        self._limiter.reserve(estimate)

        try:
            response = self._call_api(prompt, max_output_tokens)
        except DailyLimitReached:
            raise
        except RateLimitError as exc:
            if self._is_daily_quota_error(exc):
                self._limiter.mark_daily_stopped("Groq daily token quota exhausted")
                raise DailyLimitReached(
                    "Groq daily token quota exhausted (reported by API)"
                ) from exc

            # One backoff attempt for per-minute Groq limits; then stop this run.
            logger.warning("Groq rate limit hit, backing off once: %s", exc)
            time.sleep(30)
            try:
                self._limiter.reserve(estimate)
                response = self._call_api(prompt, max_output_tokens)
            except RateLimitError as retry_exc:
                self._limiter.mark_daily_stopped("repeated Groq rate-limit responses")
                raise RateLimitStop(
                    "Groq rate limit persisted after backoff; stopping LLM pass"
                ) from retry_exc
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("Transient Groq API error: %s", exc)
            time.sleep(5)
            self._limiter.reserve(estimate)
            response = self._call_api(prompt, max_output_tokens)

        content = response.choices[0].message.content or ""
        total_tokens = getattr(getattr(response, "usage", None), "total_tokens", estimate)
        self._limiter.record(int(total_tokens or estimate))
        set_cached(prompt, content, GROQ_MODEL)
        return content

    def _call_api(self, prompt: str, max_output_tokens: int):
        return self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You return only valid compact JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=max_output_tokens,
        )

    @staticmethod
    def _is_daily_quota_error(exc: RateLimitError) -> bool:
        """True when Groq reports the daily token/request quota is exhausted."""
        message = str(exc).lower()
        return "tokens per day" in message or "tpd" in message


def get_optional_client() -> GroqLLMClient | None:
    """Return a client when configured; otherwise log and return None."""
    try:
        return GroqLLMClient()
    except LLMUnavailable as exc:
        logger.warning("LLM disabled: %s", exc)
        return None
    except Exception as exc:
        logger.warning("LLM disabled due to client initialisation error: %s", exc)
        return None


__all__ = [
    "DailyLimitReached",
    "GroqLLMClient",
    "RateLimitStop",
    "get_optional_client",
]
