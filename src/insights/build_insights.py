"""Phase 4 — Insight extraction.

Precomputes aggregate rows for the dashboard from enriched_reviews.

The dashboard can still drill into individual reviews through example_ids, but
this phase keeps charts and top lists fast by materialising the common queries
into the insights table.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.config import EXPORTS_DIR
from src.db import get_connection, init_db

logger = logging.getLogger(__name__)

MAX_EXAMPLES = 5
MAX_INSIGHTS_PER_TYPE = 25

THEME_TO_INSIGHT_TYPE = {
    "DISCOVERY_PROBLEMS": "discovery_problem",
    "RECOMMENDATION_FRUSTRATIONS": "frustration",
    "LISTENING_GOALS": "listening_goal",
    "REPEAT_LISTENING_CAUSES": "repeat_cause",
}

OPPORTUNITY_THEMES = {
    "UNMET_NEEDS",
    "DISCOVERY_PROBLEMS",
    "RECOMMENDATION_FRUSTRATIONS",
    "REPEAT_LISTENING_CAUSES",
}

OPPORTUNITY_DEFINITIONS = [
    {
        "label": "Hidden Gem Discovery Mode",
        "summary": (
            "Create a dedicated mode for high-fit tracks from emerging artists, smaller "
            "catalogs, and songs outside the user's usual popularity band."
        ),
        "keywords": [
            "hidden gem", "underground", "new artist", "unknown artist", "small artist",
            "less popular", "popularity", "mainstream", "discover", "new music",
        ],
        "themes": {"UNMET_NEEDS", "DISCOVERY_PROBLEMS"},
    },
    {
        "label": "Freshness Controls for Recommendations",
        "summary": (
            "Let users tune how much fresh, unfamiliar music appears in recommendations "
            "so discovery does not collapse into the same tracks."
        ),
        "keywords": [
            "same songs", "same tracks", "repetitive", "repeat", "stale",
            "nothing new", "fresh", "new recommendations", "again", "loop",
        ],
        "themes": {"REPEAT_LISTENING_CAUSES", "RECOMMENDATION_FRUSTRATIONS"},
    },
    {
        "label": "Exclude Known Artists From Discovery",
        "summary": (
            "Add a discovery filter that suppresses followed, liked, or heavily played "
            "artists when the user is explicitly trying to find something new."
        ),
        "keywords": [
            "already know", "already follow", "known artists", "same artists",
            "exclude", "block artist", "liked songs", "followed artists",
        ],
        "themes": {"UNMET_NEEDS", "DISCOVERY_PROBLEMS", "REPEAT_LISTENING_CAUSES"},
    },
    {
        "label": "\"Surprise Me\" Shuffle",
        "summary": (
            "Offer a shuffle mode that intentionally explores adjacent genres, eras, "
            "and artists while staying relevant to the current listening context."
        ),
        "keywords": [
            "shuffle", "surprise", "random", "mix", "different", "variety",
            "explore", "unexpected", "new song",
        ],
        "themes": {"UNMET_NEEDS", "REPEAT_LISTENING_CAUSES"},
    },
    {
        "label": "Mood-Based Discovery Paths",
        "summary": (
            "Guide discovery by mood, activity, and listening intent instead of relying "
            "only on genre or historical similarity."
        ),
        "keywords": [
            "mood", "vibe", "activity", "workout", "study", "focus", "relax",
            "party", "road trip", "context", "genre",
        ],
        "themes": {"LISTENING_GOALS", "UNMET_NEEDS", "DISCOVERY_PROBLEMS"},
    },
    {
        "label": "Monthly Discovery Goals",
        "summary": (
            "Give users lightweight goals such as finding five new artists or saving "
            "ten unfamiliar tracks each month."
        ),
        "keywords": [
            "goal", "monthly", "challenge", "new artists", "new songs",
            "find new", "save", "discover more",
        ],
        "themes": {"LISTENING_GOALS", "UNMET_NEEDS"},
    },
    {
        "label": "Popularity Filter in Search",
        "summary": (
            "Add popularity controls in search and discovery feeds so users can choose "
            "mainstream, niche, or balanced results."
        ),
        "keywords": [
            "search", "popularity", "popular", "underground", "mainstream",
            "niche", "filter", "sort", "less known",
        ],
        "themes": {"UNMET_NEEDS", "DISCOVERY_PROBLEMS"},
    },
    {
        "label": "Discovery Intent Onboarding",
        "summary": (
            "Ask users what kind of discovery they want, then use that preference to "
            "shape recommendations and reduce irrelevant repeats."
        ),
        "keywords": [
            "onboarding", "preference", "ask me", "what i want", "intent",
            "taste", "personalize", "set up", "recommend",
        ],
        "themes": {"UNMET_NEEDS", "RECOMMENDATION_FRUSTRATIONS"},
    },
    {
        "label": "Repeat Fatigue Reset",
        "summary": (
            "Add a reset action for users who feel their recommendations are stuck, "
            "temporarily down-weighting overplayed tracks and artists."
        ),
        "keywords": [
            "reset", "stuck", "overplayed", "same", "repetitive", "boring",
            "change", "refresh", "recommendations", "algorithm",
        ],
        "themes": {"REPEAT_LISTENING_CAUSES", "RECOMMENDATION_FRUSTRATIONS"},
    },
    {
        "label": "Discovery Parity for Free Tier",
        "summary": (
            "Improve free-tier discovery quality so meaningful exploration is not "
            "perceived as gated behind Premium."
        ),
        "keywords": [
            "free", "premium", "pay", "paid", "tier", "gated", "subscription",
            "recommendations", "limited",
        ],
        "themes": {"UNMET_NEEDS", "DISCOVERY_PROBLEMS", "RECOMMENDATION_FRUSTRATIONS"},
    },
]


@dataclass(frozen=True)
class InsightStats:
    enriched_rows: int
    insight_rows: int
    export_path: Path


def _load_enriched_rows() -> list[dict]:
    """Load enriched review rows with metadata needed for aggregation."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                e.id,
                e.sentiment,
                e.sentiment_score,
                e.topic_label,
                e.topic_confidence,
                e.theme,
                e.segments,
                c.clean_text,
                c.source,
                c.date
            FROM enriched_reviews e
            JOIN clean_reviews c ON c.id = e.id
            ORDER BY c.date DESC, e.id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _display_label(raw_label: str | None) -> str:
    """Turn topic labels into cleaner dashboard labels."""
    label = (raw_label or "General Feedback").strip()
    match = re.match(r"Topic\s+\d+:\s*(.*)", label)
    if match:
        label = match.group(1)
    label = re.sub(r"\s+", " ", label).strip(" ,-")
    return label.title() if label else "General Feedback"


def _parse_segments(raw_segments: str | None) -> list[str]:
    """Return segment names from JSON stored in enriched_reviews.segments."""
    if not raw_segments:
        return ["Unknown"]
    try:
        parsed = json.loads(raw_segments)
    except json.JSONDecodeError:
        return ["Unknown"]
    if not isinstance(parsed, list):
        return ["Unknown"]
    segments = [
        str(item.get("segment", "Unknown"))
        for item in parsed
        if isinstance(item, dict) and item.get("segment")
    ]
    return segments or ["Unknown"]


def _summary_for(insight_type: str, label: str, count: int) -> str:
    """Create a short deterministic summary when LLM synthesis is skipped."""
    readable_type = insight_type.replace("_", " ")
    return f"{count} reviews mention {label.lower()} as {readable_type} feedback."


def _build_theme_topic_insights(rows: list[dict]) -> list[dict]:
    """Aggregate product-question insights by theme and topic."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        insight_type = THEME_TO_INSIGHT_TYPE.get(row.get("theme"))
        if not insight_type:
            continue
        label = _display_label(row.get("topic_label"))
        grouped[(insight_type, label)].append(row)

    insights: list[dict] = []
    for (insight_type, label), items in grouped.items():
        # Pick representative examples: negative/neutral first for problems,
        # then most recent based on the query ordering.
        if insight_type in {"discovery_problem", "frustration", "repeat_cause"}:
            items = sorted(items, key=lambda r: (r.get("sentiment") != "negative", r["date"]))

        count = len(items)
        example_ids = [item["id"] for item in items[:MAX_EXAMPLES]]
        insights.append(
            {
                "insight_type": insight_type,
                "label": label,
                "count": count,
                "example_ids": json.dumps(example_ids),
                "summary": _summary_for(insight_type, label, count),
            }
        )

    return _top_per_type(insights)


def _opportunity_match_score(row: dict, definition: dict) -> int:
    """Score how strongly a review supports a solution opportunity."""
    theme = row.get("theme")
    if theme not in definition["themes"] or theme not in OPPORTUNITY_THEMES:
        return 0

    haystack = " ".join(
        [
            str(row.get("clean_text") or ""),
            str(row.get("topic_label") or ""),
        ]
    ).lower()
    keyword_matches = sum(1 for keyword in definition["keywords"] if keyword in haystack)
    if keyword_matches == 0:
        return 0
    return 2 + keyword_matches


def _build_solution_opportunities(rows: list[dict]) -> list[dict]:
    """Build solution-oriented opportunities from unmet needs and discovery friction."""
    insights = []
    for definition in OPPORTUNITY_DEFINITIONS:
        scored = []
        for row in rows:
            score = _opportunity_match_score(row, definition)
            if score > 0:
                scored.append((score, row))

        if not scored:
            continue

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].get("sentiment") != "negative",
                item[1].get("date") or "",
            )
        )
        example_ids = []
        for _, row in scored:
            if row["id"] not in example_ids:
                example_ids.append(row["id"])
            if len(example_ids) == MAX_EXAMPLES:
                break

        insights.append(
            {
                "insight_type": "opportunity",
                "label": definition["label"],
                "count": len({row["id"] for _, row in scored}),
                "example_ids": json.dumps(example_ids),
                "summary": definition["summary"],
            }
        )

    insights.sort(key=lambda row: (-row["count"], row["label"]))
    return insights[:10]


def _build_segment_insights(rows: list[dict]) -> list[dict]:
    """Aggregate review counts by inferred user segment."""
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        for segment in _parse_segments(row.get("segments")):
            counts[segment] += 1
            if len(examples[segment]) < MAX_EXAMPLES:
                examples[segment].append(row["id"])

    insights = []
    for segment, count in counts.most_common(MAX_INSIGHTS_PER_TYPE):
        insights.append(
            {
                "insight_type": "segment",
                "label": segment,
                "count": count,
                "example_ids": json.dumps(examples[segment]),
                "summary": f"{count} reviews are associated with the {segment.lower()} segment.",
            }
        )
    return insights


def _build_segment_theme_insights(rows: list[dict]) -> list[dict]:
    """Aggregate theme pain points by segment for dashboard comparisons."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        theme = row.get("theme")
        if theme not in THEME_TO_INSIGHT_TYPE:
            continue
        for segment in _parse_segments(row.get("segments")):
            grouped[(segment, theme)].append(row)

    insights = []
    for (segment, theme), items in grouped.items():
        count = len(items)
        label = f"{segment} - {theme}"
        insights.append(
            {
                "insight_type": "segment_theme",
                "label": label,
                "count": count,
                "example_ids": json.dumps([item["id"] for item in items[:MAX_EXAMPLES]]),
                "summary": f"{count} {segment.lower()} reviews map to {theme.lower()} feedback.",
            }
        )
    return _top_per_type(insights)


def _build_sentiment_insights(rows: list[dict]) -> list[dict]:
    """Aggregate sentiment counts for overview cards/charts."""
    counts = Counter(row.get("sentiment") or "unknown" for row in rows)
    examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        sentiment = row.get("sentiment") or "unknown"
        if len(examples[sentiment]) < MAX_EXAMPLES:
            examples[sentiment].append(row["id"])

    return [
        {
            "insight_type": "sentiment",
            "label": sentiment,
            "count": count,
            "example_ids": json.dumps(examples[sentiment]),
            "summary": f"{count} reviews are {sentiment}.",
        }
        for sentiment, count in counts.most_common()
    ]


def _top_per_type(insights: Iterable[dict]) -> list[dict]:
    """Keep only the top N rows per insight_type."""
    by_type: dict[str, list[dict]] = defaultdict(list)
    for insight in insights:
        by_type[insight["insight_type"]].append(insight)

    trimmed: list[dict] = []
    for insight_type, rows in by_type.items():
        rows.sort(key=lambda row: row["count"], reverse=True)
        trimmed.extend(rows[:MAX_INSIGHTS_PER_TYPE])
    return trimmed


def _write_insights(insights: list[dict]) -> None:
    """Replace the insights table with freshly computed rows."""
    with get_connection() as conn:
        conn.execute("DELETE FROM insights")
        conn.executemany(
            """
            INSERT INTO insights (insight_type, label, count, example_ids, summary)
            VALUES (:insight_type, :label, :count, :example_ids, :summary)
            """,
            insights,
        )


def _export_insights(insights: list[dict]) -> Path:
    """Write a CSV snapshot for easy inspection outside SQLite."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / "insights.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["insight_type", "label", "count", "example_ids", "summary"],
        )
        writer.writeheader()
        writer.writerows(insights)
    return path


def run() -> InsightStats:
    """Build insight aggregates from enriched_reviews."""
    init_db()
    rows = _load_enriched_rows()
    logger.info("Phase 4: loaded %d enriched reviews", len(rows))

    insights: list[dict] = []
    insights.extend(_build_theme_topic_insights(rows))
    insights.extend(_build_solution_opportunities(rows))
    insights.extend(_build_segment_insights(rows))
    insights.extend(_build_segment_theme_insights(rows))
    insights.extend(_build_sentiment_insights(rows))

    # Stable ordering makes the table and export easy to inspect.
    insights.sort(key=lambda row: (row["insight_type"], -row["count"], row["label"]))

    _write_insights(insights)
    export_path = _export_insights(insights)

    logger.info("Phase 4 complete: wrote %d insights", len(insights))
    logger.info("Phase 4 export: %s", export_path)

    return InsightStats(
        enriched_rows=len(rows),
        insight_rows=len(insights),
        export_path=export_path,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
