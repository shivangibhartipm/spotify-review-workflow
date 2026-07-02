"""
Phase 2 — Data cleaning.

Reads raw_reviews and rebuilds clean_reviews with:
- duplicate removal
- URL removal
- emoji removal
- light normalization
- English language detection/filtering

The raw_reviews table is never modified.
"""

from __future__ import annotations

import hashlib
import logging
import re
import string
from dataclasses import dataclass

import emoji
from langdetect import LangDetectException, detect

from src.db import get_connection, init_db

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
REPEATED_PUNCT_RE = re.compile(r"([!?.,])\1+")

# Small built-in fallback keeps Phase 2 runnable without requiring an NLTK
# download at runtime. Stopword-stripped text is used only for dedupe hashing,
# while clean_text remains readable for downstream review display.
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
}


@dataclass(frozen=True)
class CleaningStats:
    raw_rows: int
    empty_rows: int
    duplicate_rows: int
    non_english_rows: int
    inserted_rows: int


def remove_urls(text: str) -> str:
    """Remove URLs from review text."""
    return URL_RE.sub(" ", text)


def remove_emojis(text: str) -> str:
    """Remove emojis from review text."""
    return emoji.replace_emoji(text, replace=" ")


def normalize_text(text: str) -> str:
    """Light normalization suitable for classification and display."""
    text = (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\ufffd", " ")
    )
    text = text.lower()
    text = REPEATED_PUNCT_RE.sub(r"\1", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def remove_stopwords(text: str) -> str:
    """Return a stopword-stripped copy for hashing/modeling support."""
    tokens = [token for token in text.split() if token not in STOPWORDS]
    return " ".join(tokens)


def dedupe_hash(text: str) -> str:
    """
    Build a stable normalized hash for exact/near duplicate detection.

    This intentionally strips punctuation and common stopwords so trivial
    formatting differences do not create duplicate clean rows.
    """
    without_punctuation = text.translate(str.maketrans("", "", string.punctuation))
    model_text = remove_stopwords(WHITESPACE_RE.sub(" ", without_punctuation).strip())
    return hashlib.sha256(model_text.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    """Detect language, returning 'unknown' when detection is unreliable."""
    if len(text.strip()) < 10:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def clean_review_text(text: str) -> str:
    """Apply text-level cleaning steps in the order from the architecture."""
    text = remove_urls(text)
    text = remove_emojis(text)
    text = normalize_text(text)
    return text


def run() -> CleaningStats:
    """
    Rebuild clean_reviews from raw_reviews.

    Rebuilding keeps Phase 2 deterministic: changes to cleaning rules are
    reflected by re-running `python run_all.py --phase 2`.
    """
    init_db()

    raw_rows = 0
    empty_rows = 0
    duplicate_rows = 0
    non_english_rows = 0
    inserted_rows = 0
    seen_hashes: set[str] = set()
    clean_rows: list[dict] = []

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, source, text, rating, date, url
            FROM raw_reviews
            ORDER BY date ASC, id ASC
            """
        ).fetchall()

        raw_rows = len(rows)
        logger.info("Phase 2: loaded %d raw reviews", raw_rows)

        for row in rows:
            original_text = (row["text"] or "").strip()
            if not original_text:
                empty_rows += 1
                continue

            clean_text = clean_review_text(original_text)
            if not clean_text:
                empty_rows += 1
                continue

            row_hash = dedupe_hash(clean_text)
            if row_hash in seen_hashes:
                duplicate_rows += 1
                continue
            seen_hashes.add(row_hash)

            language = detect_language(clean_text)
            if language != "en":
                non_english_rows += 1
                continue

            clean_rows.append(
                {
                    "id": row["id"],
                    "source": row["source"],
                    "rating": row["rating"],
                    "date": row["date"],
                    "url": row["url"],
                    "clean_text": clean_text,
                    "language": language,
                }
            )

        # Rebuild downstream tables in FK order: enriched_reviews references
        # clean_reviews, so clear enrichment before replacing clean rows.
        conn.execute("DELETE FROM enriched_reviews")
        conn.execute("DELETE FROM clean_reviews")
        conn.executemany(
            """
            INSERT INTO clean_reviews
                (id, source, rating, date, url, clean_text, language)
            VALUES
                (:id, :source, :rating, :date, :url, :clean_text, :language)
            """,
            clean_rows,
        )
        inserted_rows = len(clean_rows)

    stats = CleaningStats(
        raw_rows=raw_rows,
        empty_rows=empty_rows,
        duplicate_rows=duplicate_rows,
        non_english_rows=non_english_rows,
        inserted_rows=inserted_rows,
    )

    logger.info(
        "Phase 2 complete: raw=%d, clean=%d, empty=%d, duplicates=%d, non_english=%d",
        stats.raw_rows,
        stats.inserted_rows,
        stats.empty_rows,
        stats.duplicate_rows,
        stats.non_english_rows,
    )
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
