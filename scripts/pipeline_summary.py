"""Pipeline summary used by local scheduler test and GitHub Actions."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reviews.db"


def main() -> int:
    if not DB_PATH.exists():
        print("reviews.db was not created")
        return 1

    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("select count(*) from enriched_reviews").fetchone()[0]
    unclassified = conn.execute(
        "select count(*) from enriched_reviews where theme='UNCLASSIFIED'"
    ).fetchone()[0]
    insights = conn.execute("select count(*) from insights").fetchone()[0]
    usage = conn.execute(
        "select requests, tokens from llm_usage where day=date('now')"
    ).fetchone()

    print(f"Enriched reviews: {total:,}")
    print(f"UNCLASSIFIED: {unclassified:,}")
    print(f"Insight rows: {insights:,}")
    if usage:
        print(f"LLM usage today: {usage[0]} requests, {usage[1]:,} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
