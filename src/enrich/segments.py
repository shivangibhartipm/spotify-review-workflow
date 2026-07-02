"""Phase 3d — Rule-based user segmentation."""

from __future__ import annotations

import json

from src.config import SEGMENT_KEYWORDS


def _score_segment(text: str, keywords: list[str]) -> int:
    text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in text)


def infer_segments(text: str) -> str:
    """
    Infer one or more user segments and return a JSON list.

    Example:
      [{"segment": "Premium Users", "confidence": 0.67}]
    """
    scored = []
    for segment, keywords in SEGMENT_KEYWORDS.items():
        score = _score_segment(text, keywords)
        if score > 0:
            confidence = min(1.0, score / max(1, len(keywords)))
            scored.append({"segment": segment, "confidence": round(confidence, 2)})

    if not scored:
        scored.append({"segment": "Unknown", "confidence": 0.0})

    scored.sort(key=lambda item: item["confidence"], reverse=True)
    return json.dumps(scored)


def infer_all(rows: list[dict]) -> dict[str, str]:
    """Return {review_id: segments_json}."""
    return {row["id"]: infer_segments(row["clean_text"]) for row in rows}
