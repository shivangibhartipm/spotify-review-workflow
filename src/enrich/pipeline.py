"""Phase 3 — Enrichment pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.db import get_connection, init_db
from src.enrich.segments import infer_all
from src.enrich.sentiment import score_all
from src.enrich.themes import classify_all
from src.enrich.topics import assign_topics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrichmentStats:
    clean_rows: int
    enriched_rows: int
    sentiment_rows: int
    topic_rows: int
    theme_rows: int
    segment_rows: int


def _load_clean_reviews() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, source, rating, date, url, clean_text, language
            FROM clean_reviews
            ORDER BY date ASC, id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def _rebuild_enriched_reviews(rows: list[dict]) -> int:
    with get_connection() as conn:
        conn.execute("DELETE FROM enriched_reviews")
        conn.executemany(
            """
            INSERT INTO enriched_reviews
                (
                    id,
                    sentiment,
                    sentiment_score,
                    topic_label,
                    topic_confidence,
                    theme,
                    segments
                )
            VALUES
                (
                    :id,
                    :sentiment,
                    :sentiment_score,
                    :topic_label,
                    :topic_confidence,
                    :theme,
                    :segments
                )
            """,
            rows,
        )
        return len(rows)


def run() -> EnrichmentStats:
    """Run all Phase 3 sub-steps and rebuild enriched_reviews."""
    init_db()
    clean_rows = _load_clean_reviews()
    logger.info("Phase 3: loaded %d clean reviews", len(clean_rows))

    if not clean_rows:
        _rebuild_enriched_reviews([])
        return EnrichmentStats(0, 0, 0, 0, 0, 0)

    sentiments = score_all(clean_rows)
    topics = assign_topics(clean_rows)

    # Attach topics to rows before theme classification so the LLM prompt can
    # use topic context for ambiguous cases.
    rows_with_topics = []
    for row in clean_rows:
        topic_label, topic_confidence = topics.get(row["id"], ("General Feedback", 0.0))
        enriched_context = dict(row)
        enriched_context["topic_label"] = topic_label
        enriched_context["topic_confidence"] = topic_confidence
        rows_with_topics.append(enriched_context)

    themes = classify_all(rows_with_topics)
    segments = infer_all(clean_rows)

    enriched_rows: list[dict] = []
    for row in rows_with_topics:
        sentiment, sentiment_score = sentiments[row["id"]]
        enriched_rows.append(
            {
                "id": row["id"],
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "topic_label": row["topic_label"],
                "topic_confidence": row["topic_confidence"],
                "theme": themes.get(row["id"], "UNCLASSIFIED"),
                "segments": segments.get(row["id"], "[]"),
            }
        )

    inserted = _rebuild_enriched_reviews(enriched_rows)
    stats = EnrichmentStats(
        clean_rows=len(clean_rows),
        enriched_rows=inserted,
        sentiment_rows=len(sentiments),
        topic_rows=len(topics),
        theme_rows=len(themes),
        segment_rows=len(segments),
    )
    logger.info("Phase 3 complete: enriched=%d", inserted)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
