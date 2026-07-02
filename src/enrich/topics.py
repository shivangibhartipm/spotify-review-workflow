"""Phase 3b — Topic modeling with TF-IDF + NMF."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

DEFAULT_TOPICS = 10

TOPIC_HINTS: dict[str, set[str]] = {
    "Music Discovery": {"discover", "new", "artist", "song", "music", "explore"},
    "Recommendations": {"recommend", "suggest", "algorithm", "mix", "radio"},
    "Search": {"search", "find", "results", "query"},
    "Playlists": {"playlist", "daily", "mix", "liked", "queue"},
    "Artist Exploration": {"artist", "album", "band", "release"},
    "Personalization": {"personal", "taste", "based", "custom", "for you"},
    "Algorithm Quality": {"algorithm", "wrong", "bad", "irrelevant", "quality"},
    "Repetitive Content": {"same", "repeat", "again", "loop", "repetitive"},
    "User Interface": {"ui", "button", "screen", "app", "interface", "design"},
}


def _label_topic(top_terms: list[str], topic_number: int) -> str:
    terms = set(top_terms)
    best_label = None
    best_score = 0

    for label, hints in TOPIC_HINTS.items():
        score = len(terms & hints)
        if score > best_score:
            best_label = label
            best_score = score

    if best_label:
        return best_label
    return f"Topic {topic_number + 1}: {', '.join(top_terms[:3])}"


def assign_topics(rows: list[dict], n_topics: int = DEFAULT_TOPICS) -> dict[str, tuple[str, float]]:
    """Return {review_id: (topic_label, confidence)}."""
    if not rows:
        return {}

    texts = [row["clean_text"] for row in rows]
    review_ids = [row["id"] for row in rows]

    # NMF needs at least 2 non-empty vocabulary items.  For tiny datasets, fall
    # back to a single generic topic rather than failing the pipeline.
    if len(texts) < 2:
        return {review_ids[0]: ("General Feedback", 1.0)}

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        min_df=2,
        max_df=0.95,
        ngram_range=(1, 2),
    )

    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return {review_id: ("General Feedback", 1.0) for review_id in review_ids}

    usable_topics = max(2, min(n_topics, matrix.shape[0] - 1, matrix.shape[1] - 1))
    model = NMF(n_components=usable_topics, init="nndsvda", random_state=42, max_iter=400)
    weights = model.fit_transform(matrix)

    feature_names = np.array(vectorizer.get_feature_names_out())
    topic_labels: list[str] = []
    for idx, component in enumerate(model.components_):
        top_indices = component.argsort()[-10:][::-1]
        top_terms = feature_names[top_indices].tolist()
        topic_labels.append(_label_topic(top_terms, idx))

    assignments: dict[str, tuple[str, float]] = {}
    for review_id, row_weights in zip(review_ids, weights):
        if row_weights.sum() == 0:
            assignments[review_id] = ("General Feedback", 0.0)
            continue
        topic_idx = int(row_weights.argmax())
        confidence = float(row_weights[topic_idx] / row_weights.sum())
        assignments[review_id] = (topic_labels[topic_idx], round(confidence, 4))

    logger.info("Topic modeling: assigned %d reviews across %d topics", len(rows), usable_topics)
    return assignments
