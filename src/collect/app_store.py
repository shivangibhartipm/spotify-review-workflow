"""
Phase 1 collector — Apple App Store reviews.

Calls the iTunes RSS customer-reviews API directly (no third-party library),
which avoids the SSL-session issues with app-store-scraper on Windows.

API endpoint:
  https://itunes.apple.com/{country}/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent/json
"""

import logging
import time
from datetime import datetime, timezone

import truststore
truststore.inject_into_ssl()  # use Windows certificate store

import requests

from src.config import (
    APP_STORE_COUNTRIES,
    SPOTIFY_APP_STORE_APP_ID,
    START_DATE,
)
from src.db import init_db, insert_raw_reviews

logger = logging.getLogger(__name__)

SOURCE = "app_store"

_ITUNES_RSS = (
    "https://itunes.apple.com/{country}/rss/customerreviews"
    "/page={page}/id={app_id}/sortby=mostrecent/json"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIReviewEngine/1.0)"}
_MAX_PAGES = 10   # iTunes RSS exposes up to 10 pages of 50 reviews each = 500/country


def _parse_date(label: str) -> datetime | None:
    """Parse ISO-8601 date string returned by the iTunes API."""
    if not label:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(label, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _is_in_window(dt: datetime | None) -> bool:
    if dt is None:
        return False
    return dt >= START_DATE


def _collect_country(country: str, app_id: str, session: requests.Session) -> list[dict]:
    rows: list[dict] = []

    for page in range(1, _MAX_PAGES + 1):
        url = _ITUNES_RSS.format(country=country, page=page, app_id=app_id)
        try:
            resp = session.get(url, timeout=15, headers=_HEADERS)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("App Store [%s] page %d: fetch error — %s", country, page, exc)
            break

        entries = data.get("feed", {}).get("entry", [])
        if not entries:
            break

        # The first entry in the feed is app metadata, not a review — skip it.
        # Real review entries have an "im:rating" field.
        review_entries = [e for e in entries if "im:rating" in e]
        if not review_entries:
            break

        oldest_on_page = None
        for entry in review_entries:
            updated_label = entry.get("updated", {}).get("label", "")
            dt = _parse_date(updated_label)

            if not _is_in_window(dt):
                continue

            if oldest_on_page is None or (dt and dt < oldest_on_page):
                oldest_on_page = dt

            review_id = entry.get("id", {}).get("label", f"{country}_{page}_{len(rows)}")
            title = entry.get("title", {}).get("label", "").strip()
            body = entry.get("content", {}).get("label", "").strip()
            full_text = f"{title}. {body}" if title and body else body or title

            if not full_text:
                continue

            rating_label = entry.get("im:rating", {}).get("label")
            rating = int(rating_label) if rating_label and rating_label.isdigit() else None

            rows.append(
                {
                    "id":     f"{SOURCE}:{country}:{review_id}",
                    "source": SOURCE,
                    "text":   full_text,
                    "rating": rating,
                    "date":   dt.isoformat() if dt else "",
                    "url":    (
                        f"https://apps.apple.com/{country}/app/spotify/id{app_id}"
                    ),
                }
            )

        # If the oldest review on this page is before our window, stop paginating.
        if oldest_on_page and oldest_on_page < START_DATE:
            break

        logger.debug("App Store [%s] page %d — %d reviews so far", country, page, len(rows))
        time.sleep(1)

    logger.info("App Store [%s]: %d reviews collected", country, len(rows))
    return rows


def collect(app_id: str = SPOTIFY_APP_STORE_APP_ID) -> int:
    """
    Collect App Store reviews for all configured storefronts.
    Returns the count of newly inserted rows.
    """
    init_db()
    logger.info("App Store: starting collection (countries: %s)", APP_STORE_COUNTRIES)

    session = requests.Session()
    all_rows: list[dict] = []

    for country in APP_STORE_COUNTRIES:
        rows = _collect_country(country, app_id, session)
        all_rows.extend(rows)
        time.sleep(2)

    inserted = insert_raw_reviews(all_rows)
    logger.info(
        "App Store: %d reviews fetched, %d newly inserted (duplicates skipped)",
        len(all_rows),
        inserted,
    )
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = collect()
    print(f"App Store: {count} new reviews inserted.")
