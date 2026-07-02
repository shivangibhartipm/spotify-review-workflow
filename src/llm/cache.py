"""SQLite-backed LLM prompt/response cache."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from src.config import GROQ_MODEL
from src.db import get_connection, init_db


def prompt_hash(prompt: str, model: str = GROQ_MODEL) -> str:
    """Return a stable hash for a model+prompt pair."""
    payload = f"{model}\n\n{prompt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached(prompt: str, model: str = GROQ_MODEL) -> str | None:
    """Return cached response text, if present."""
    init_db()
    key = prompt_hash(prompt, model)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT response FROM llm_cache WHERE prompt_hash = ?",
            (key,),
        ).fetchone()
        return row["response"] if row else None


def set_cached(prompt: str, response: str, model: str = GROQ_MODEL) -> None:
    """Store a prompt/response pair."""
    init_db()
    key = prompt_hash(prompt, model)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache (prompt_hash, response, created_at)
            VALUES (?, ?, ?)
            """,
            (key, response, datetime.now(timezone.utc).isoformat()),
        )
