"""
Phase 1 collector — Spotify Community forums.

Uses the Khoros v1 REST API (community.spotify.com/restapi/vc/...).
Collects topic subject + teaser text directly from the board listing call —
no per-thread follow-up requests needed, so the whole collector runs in ~1 min.

Boards collected:
  ideas_live          — live feature ideas  (unmet needs, discovery wishes)
  ongoing_issues      — active issues        (frustrations)
  ideas_no            — closed/declined ideas (persistent unmet needs)
  ideas_implemented   — implemented ideas    (historical demand)
"""

import logging
import time
from datetime import datetime, timezone

import truststore
truststore.inject_into_ssl()   # use Windows certificate store

import requests

from src.config import START_DATE
from src.db import init_db, insert_raw_reviews

logger = logging.getLogger(__name__)

SOURCE = "forum"

_BASE = "https://community.spotify.com/restapi/vc"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIReviewEngine/1.0)"}

_BOARDS = [
    ("ideas_live",         "Live Ideas"),
    ("ongoing_issues",     "Ongoing Issues"),
    ("ideas_no",           "Closed Ideas"),
    ("ideas_implemented",  "Implemented Ideas"),
]

_PAGE_SIZE = 50
_MAX_PAGES = 20     # up to 1,000 topics per board
_REQUEST_DELAY = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str(node) -> str:
    """Extract the string value from a Khoros API response node."""
    if node is None:
        return ""
    if isinstance(node, dict):
        return str(node.get("$", "") or "")
    return str(node)


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _in_window(raw: str) -> bool:
    dt = _parse_date(raw)
    return dt is not None and dt >= START_DATE


def _get_json(session: requests.Session, url: str) -> dict | None:
    try:
        resp = session.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Forum API error %s — %s", url[-80:], exc)
        return None


# ---------------------------------------------------------------------------
# Board collector — listing-only (no per-topic fetches)
# ---------------------------------------------------------------------------

def _collect_board(session: requests.Session, board_id: str, board_label: str) -> list[dict]:
    rows: list[dict] = []

    for page in range(1, _MAX_PAGES + 1):
        url = (
            f"{_BASE}/boards/id/{board_id}/topics"
            f"?restapi.response_format=json"
            f"&page_size={_PAGE_SIZE}"
            f"&page={page}"
            f"&sort_order=post_time.desc"
        )
        data = _get_json(session, url)
        if not data:
            break

        messages = data.get("response", {}).get("node_message_context", {}).get("message", [])
        if isinstance(messages, dict):
            messages = [messages]
        if not messages:
            break

        oldest_on_page: datetime | None = None
        for msg in messages:
            post_time = _str(msg.get("post_time"))
            dt = _parse_date(post_time)
            if dt and (oldest_on_page is None or dt < oldest_on_page):
                oldest_on_page = dt

            if not _in_window(post_time):
                continue

            subject = _str(msg.get("subject")).strip()
            teaser  = _str(msg.get("teaser")).strip()
            status  = _str(msg.get("message_status", {}).get("name") if isinstance(msg.get("message_status"), dict) else {})
            kudos   = msg.get("kudos", {}).get("count", {})
            kudos_n = int(_str(kudos)) if _str(kudos).isdigit() else 0

            # Build the text: subject + teaser + status tag
            parts = [subject]
            if teaser:
                parts.append(teaser)
            if status:
                parts.append(f"[{status}]")
            if kudos_n:
                parts.append(f"[{kudos_n} votes]")
            full_text = " — ".join(parts)
            if not full_text.strip():
                continue

            msg_id = _str(msg.get("id"))
            raw_href = msg.get("href", "")
            if isinstance(raw_href, dict):
                raw_href = raw_href.get("$", "")
            url_path = str(raw_href).replace("/messages/id/", "").strip("/")

            rows.append({
                "id":     f"{SOURCE}:{msg_id or url_path}",
                "source": SOURCE,
                "text":   full_text,
                "rating": None,
                "date":   post_time,
                "url":    f"https://community.spotify.com/t5/p/{msg_id or url_path}",
            })

        logger.debug("Forum [%s] page %d — %d rows so far", board_id, page, len(rows))

        if oldest_on_page and oldest_on_page < START_DATE:
            break

        time.sleep(_REQUEST_DELAY)

    logger.info("Forum [%s] (%s): %d topics collected", board_id, board_label, len(rows))
    return rows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def collect() -> int:
    """
    Collect Spotify Community forum topics within the 90-day window.
    Returns the count of newly inserted rows.
    """
    init_db()
    logger.info("Forum: starting collection (%d boards)", len(_BOARDS))

    session = requests.Session()
    all_rows: list[dict] = []

    for board_id, board_label in _BOARDS:
        rows = _collect_board(session, board_id, board_label)
        all_rows.extend(rows)

    inserted = insert_raw_reviews(all_rows)
    logger.info(
        "Forum: %d topics collected, %d newly inserted (duplicates skipped)",
        len(all_rows),
        inserted,
    )
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = collect()
    print(f"Forum: {count} new topics inserted.")
