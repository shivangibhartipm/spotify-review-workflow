"""
SQLite helpers — connection, table creation, and common upsert/read operations.
All pipeline phases go through these helpers; nothing else imports sqlite3 directly.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import DB_PATH

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@contextmanager
def get_connection(db_path: Path = DB_PATH):
    """Yield a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Table creation (idempotent — safe to call on every startup)
# ---------------------------------------------------------------------------

_CREATE_RAW_REVIEWS = """
CREATE TABLE IF NOT EXISTS raw_reviews (
    id           TEXT PRIMARY KEY,   -- source:native_id
    source       TEXT NOT NULL,      -- app_store | play_store | forum
    text         TEXT NOT NULL,
    rating       INTEGER,            -- 1-5 where available, else NULL
    date         TEXT NOT NULL,      -- ISO-8601 date string
    url          TEXT,
    collected_at TEXT NOT NULL       -- ISO-8601 timestamp of ingestion
);
"""

_CREATE_CLEAN_REVIEWS = """
CREATE TABLE IF NOT EXISTS clean_reviews (
    id           TEXT PRIMARY KEY REFERENCES raw_reviews(id),
    source       TEXT NOT NULL,
    rating       INTEGER,
    date         TEXT NOT NULL,
    url          TEXT,
    clean_text   TEXT NOT NULL,
    language     TEXT NOT NULL
);
"""

_CREATE_ENRICHED_REVIEWS = """
CREATE TABLE IF NOT EXISTS enriched_reviews (
    id                TEXT PRIMARY KEY REFERENCES clean_reviews(id),
    sentiment         TEXT,          -- positive | neutral | negative
    sentiment_score   REAL,          -- -1.0 to 1.0
    topic_label       TEXT,          -- from topic model
    topic_confidence  REAL,          -- 0.0 to 1.0
    theme             TEXT,          -- one of the 5 business themes
    segments          TEXT           -- JSON list of {segment, confidence}
);
"""

_CREATE_INSIGHTS = """
CREATE TABLE IF NOT EXISTS insights (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT NOT NULL,      -- discovery_problem | frustration | opportunity | listening_goal
    label        TEXT NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    example_ids  TEXT,               -- JSON list of raw review ids
    summary      TEXT                -- optional LLM-generated one-liner
);
"""

_CREATE_LLM_CACHE = """
CREATE TABLE IF NOT EXISTS llm_cache (
    prompt_hash  TEXT PRIMARY KEY,   -- SHA-256 of (model + prompt)
    response     TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""

_CREATE_LLM_USAGE = """
CREATE TABLE IF NOT EXISTS llm_usage (
    day      TEXT PRIMARY KEY,       -- YYYY-MM-DD
    requests INTEGER NOT NULL DEFAULT 0,
    tokens   INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_raw_source  ON raw_reviews (source);",
    "CREATE INDEX IF NOT EXISTS idx_raw_date    ON raw_reviews (date);",
    "CREATE INDEX IF NOT EXISTS idx_clean_lang  ON clean_reviews (language);",
    "CREATE INDEX IF NOT EXISTS idx_enrich_theme ON enriched_reviews (theme);",
    "CREATE INDEX IF NOT EXISTS idx_enrich_sent  ON enriched_reviews (sentiment);",
]


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables and indexes.  Safe to call multiple times."""
    with get_connection(db_path) as conn:
        conn.execute(_CREATE_RAW_REVIEWS)
        conn.execute(_CREATE_CLEAN_REVIEWS)
        conn.execute(_CREATE_ENRICHED_REVIEWS)
        conn.execute(_CREATE_INSIGHTS)
        conn.execute(_CREATE_LLM_CACHE)
        conn.execute(_CREATE_LLM_USAGE)
        for idx in _CREATE_INDEXES:
            conn.execute(idx)


# ---------------------------------------------------------------------------
# Phase 1 helpers — raw_reviews
# ---------------------------------------------------------------------------

def insert_raw_reviews(rows: list[dict[str, Any]], db_path: Path = DB_PATH) -> int:
    """
    INSERT OR IGNORE a list of raw review dicts into raw_reviews.
    Returns the number of rows actually inserted (new, non-duplicate rows).

    Expected keys per row: id, source, text, rating, date, url
    `collected_at` is filled automatically.
    """
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with get_connection(db_path) as conn:
        for row in rows:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO raw_reviews
                    (id, source, text, rating, date, url, collected_at)
                VALUES
                    (:id, :source, :text, :rating, :date, :url, :collected_at)
                """,
                {
                    "id":           row["id"],
                    "source":       row["source"],
                    "text":         row["text"],
                    "rating":       row.get("rating"),
                    "date":         row["date"],
                    "url":          row.get("url", ""),
                    "collected_at": now,
                },
            )
            inserted += cursor.rowcount
    return inserted


def count_raw_reviews(source: str | None = None, db_path: Path = DB_PATH) -> int:
    """Return total raw reviews, optionally filtered by source."""
    with get_connection(db_path) as conn:
        if source:
            row = conn.execute(
                "SELECT COUNT(*) FROM raw_reviews WHERE source = ?", (source,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM raw_reviews").fetchone()
        return row[0]


def fetch_raw_reviews(
    source: str | None = None,
    db_path: Path = DB_PATH,
) -> list[sqlite3.Row]:
    """Fetch all raw reviews, optionally filtered by source."""
    with get_connection(db_path) as conn:
        if source:
            return conn.execute(
                "SELECT * FROM raw_reviews WHERE source = ? ORDER BY date DESC",
                (source,),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM raw_reviews ORDER BY date DESC"
        ).fetchall()
