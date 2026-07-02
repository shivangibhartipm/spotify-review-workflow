"""Phase 3c — Hybrid rule-based + LLM theme classification."""

from __future__ import annotations

import json
import logging
import re

from src.config import BATCH_SIZE, MAX_REVIEW_TOKENS, THEME_KEYWORDS
from src.llm.client import DailyLimitReached, RateLimitStop, get_optional_client
from src.llm.prompts import THEMES, build_theme_batch_prompt
from src.llm.rate_limiter import LLMRateLimiter

logger = logging.getLogger(__name__)

VALID_THEMES = set(THEMES)
UNCLASSIFIED = "UNCLASSIFIED"


def _keyword_score(text: str, keywords: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(keyword.lower()) for keyword in keywords)


def classify_with_rules(text: str) -> tuple[str, float, bool]:
    """
    Return (theme, confidence, is_confident).

    A rule result is confident when one theme clearly wins.  Ties and zero
    matches are sent to the LLM layer when available.
    """
    scores = {
        theme: _keyword_score(text, keywords)
        for theme, keywords in THEME_KEYWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_theme, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score == 0:
        return UNCLASSIFIED, 0.0, False

    confidence = best_score / max(1, best_score + second_score)
    is_confident = best_score > second_score
    return best_theme, round(float(confidence), 4), is_confident


def _extract_json_array(raw: str) -> list[dict]:
    """Parse a model response that should contain a JSON array."""
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _batches(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def classify_all(rows: list[dict]) -> dict[str, str]:
    """
    Return {review_id: theme}.

    Rules run first.  Low-confidence items are sent to Groq only when
    GROQ_API_KEY is configured.  If the LLM is unavailable or the daily limit is
    reached, unresolved items remain UNCLASSIFIED.
    """
    assignments: dict[str, str] = {}
    low_confidence: list[dict] = []

    for row in rows:
        theme, _, confident = classify_with_rules(row["clean_text"])
        assignments[row["id"]] = theme
        if not confident:
            low_confidence.append(row)

    logger.info(
        "Theme rules: confident=%d, low_confidence=%d",
        len(rows) - len(low_confidence),
        len(low_confidence),
    )

    if not low_confidence:
        return assignments

    limiter = LLMRateLimiter()
    if limiter.is_daily_limit_reached():
        logger.warning(
            "Theme LLM pass skipped: daily Groq budget already exhausted "
            "(%d requests, %d tokens used today)",
            *limiter.get_usage(),
        )
        return assignments

    client = get_optional_client()
    if client is None:
        logger.warning(
            "Theme LLM pass skipped; %d reviews remain %s",
            len(low_confidence),
            UNCLASSIFIED,
        )
        return assignments

    llm_classified = 0
    batches = _batches(low_confidence, BATCH_SIZE)
    logger.info("Theme LLM: processing up to %d batches", len(batches))

    for batch_index, batch in enumerate(batches, start=1):
        if limiter.is_daily_limit_reached():
            logger.warning(
                "Theme LLM pass stopped before batch %d/%d: daily limit reached",
                batch_index,
                len(batches),
            )
            break

        prompt = build_theme_batch_prompt(batch, MAX_REVIEW_TOKENS)
        try:
            raw = client.complete_json(prompt)
        except (DailyLimitReached, RateLimitStop) as exc:
            logger.warning("Theme LLM pass stopped: %s", exc)
            break
        except Exception as exc:
            logger.warning("Theme LLM batch %d failed: %s", batch_index, exc)
            continue

        for item in _extract_json_array(raw):
            review_id = str(item.get("id", ""))
            theme = str(item.get("theme", "")).strip()
            if review_id in assignments and theme in VALID_THEMES:
                assignments[review_id] = theme
                llm_classified += 1

    logger.info("Theme LLM: classified %d low-confidence reviews", llm_classified)
    return assignments
