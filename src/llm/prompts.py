"""Prompt builders for LLM-backed enrichment."""

from __future__ import annotations

import json

THEMES = [
    "DISCOVERY_PROBLEMS",
    "RECOMMENDATION_FRUSTRATIONS",
    "LISTENING_GOALS",
    "REPEAT_LISTENING_CAUSES",
    "UNMET_NEEDS",
]


def truncate_review(text: str, max_tokens: int) -> str:
    """Approximate token truncation by words."""
    words = text.split()
    return " ".join(words[:max_tokens])


def build_theme_batch_prompt(rows: list[dict], max_review_tokens: int) -> str:
    """Build a compact JSON-only theme classification prompt."""
    payload = [
        {
            "id": row["id"],
            "text": truncate_review(row["clean_text"], max_review_tokens),
            "topic": row.get("topic_label", ""),
        }
        for row in rows
    ]

    return (
        "Classify Spotify review feedback into exactly one business theme.\n"
        "Return only valid JSON. No markdown. No explanation.\n\n"
        f"Allowed themes: {', '.join(THEMES)}\n\n"
        "Return format:\n"
        "[{\"id\":\"review_id\",\"theme\":\"DISCOVERY_PROBLEMS\",\"confidence\":0.82}]\n\n"
        "Guidance:\n"
        "- DISCOVERY_PROBLEMS: hard to find new music, artists, genres, playlists.\n"
        "- RECOMMENDATION_FRUSTRATIONS: bad, repetitive, irrelevant recommendations.\n"
        "- LISTENING_GOALS: what the user wants to do while listening.\n"
        "- REPEAT_LISTENING_CAUSES: why the user hears the same content repeatedly.\n"
        "- UNMET_NEEDS: feature requests, missing capabilities, product opportunities.\n\n"
        "Reviews JSON:\n"
        f"{json.dumps(payload, ensure_ascii=True)}"
    )
