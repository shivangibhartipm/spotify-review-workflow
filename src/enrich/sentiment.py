"""Phase 3a — Sentiment scoring with VADER."""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_ANALYZER = SentimentIntensityAnalyzer()


def score_sentiment(text: str) -> tuple[str, float]:
    """Return (label, compound_score) for one review."""
    score = float(_ANALYZER.polarity_scores(text or "")["compound"])
    if score >= 0.05:
        return "positive", score
    if score <= -0.05:
        return "negative", score
    return "neutral", score


def score_all(rows: list[dict]) -> dict[str, tuple[str, float]]:
    """Return {review_id: (sentiment, score)}."""
    return {row["id"]: score_sentiment(row["clean_text"]) for row in rows}
