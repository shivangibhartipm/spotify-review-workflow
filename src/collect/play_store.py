"""
Phase 1 collector — Google Play Store reviews.

Fetches Spotify Android reviews newest-first and stops once reviews fall
outside the configured 90-day window.  Inserts into raw_reviews via db.py.
"""

import logging
import time
from datetime import timezone

from google_play_scraper import Sort, reviews as gp_reviews
from google_play_scraper.exceptions import NotFoundError

from src.config import (
    PLAY_STORE_COUNTRY,
    PLAY_STORE_FETCH_COUNT,
    PLAY_STORE_LANG,
    SPOTIFY_PLAY_STORE_APP_ID,
    START_DATE,
)
from src.db import init_db, insert_raw_reviews

logger = logging.getLogger(__name__)

SOURCE = "play_store"


def _make_id(review_id: str) -> str:
    return f"{SOURCE}:{review_id}"


def _parse_date(review: dict) -> str:
    """Return the review date as an ISO-8601 string (UTC)."""
    dt = review.get("at")
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _is_in_window(review: dict) -> bool:
    dt = review.get("at")
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= START_DATE


def collect(app_id: str = SPOTIFY_PLAY_STORE_APP_ID) -> int:
    """
    Collect Play Store reviews for `app_id` within the 90-day window.
    Returns the count of newly inserted rows.
    """
    init_db()
    logger.info("Play Store: starting collection for %s", app_id)

    rows: list[dict] = []
    continuation_token = None
    total_fetched = 0
    out_of_window = False

    while not out_of_window:
        batch_size = min(200, PLAY_STORE_FETCH_COUNT - total_fetched)
        if batch_size <= 0:
            break

        try:
            result, continuation_token = gp_reviews(
                app_id,
                lang=PLAY_STORE_LANG,
                country=PLAY_STORE_COUNTRY,
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
        except NotFoundError:
            logger.error("Play Store: app %s not found", app_id)
            break
        except Exception as exc:
            logger.error("Play Store: fetch error — %s", exc)
            break

        if not result:
            break

        for review in result:
            if not _is_in_window(review):
                out_of_window = True
                break

            text = (review.get("content") or "").strip()
            if not text:
                continue

            rows.append(
                {
                    "id":     _make_id(review["reviewId"]),
                    "source": SOURCE,
                    "text":   text,
                    "rating": review.get("score"),
                    "date":   _parse_date(review),
                    "url":    (
                        f"https://play.google.com/store/apps/details"
                        f"?id={app_id}&reviewId={review['reviewId']}"
                    ),
                }
            )

        total_fetched += len(result)
        logger.info("Play Store: fetched %d reviews so far", total_fetched)

        if continuation_token is None:
            break

        time.sleep(1)

    inserted = insert_raw_reviews(rows)
    logger.info(
        "Play Store: %d reviews fetched, %d newly inserted (duplicates skipped)",
        len(rows),
        inserted,
    )
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = collect()
    print(f"Play Store: {count} new reviews inserted.")
