"""
Central configuration for the Review Discovery Engine.
All tunable settings live here — no magic numbers scattered across scripts.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "reviews.db"
EXPORTS_DIR = DATA_DIR / "exports"

DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Collection window
# ---------------------------------------------------------------------------
LOOKBACK_DAYS = 90
START_DATE = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

# ---------------------------------------------------------------------------
# Spotify app identifiers
# ---------------------------------------------------------------------------
SPOTIFY_PLAY_STORE_APP_ID = "com.spotify.music"
SPOTIFY_APP_STORE_APP_ID = "324684580"      # Spotify iOS app ID on the App Store
APP_STORE_COUNTRIES = ["us", "gb", "au", "ca", "in"]   # fetch reviews from these storefronts

# ---------------------------------------------------------------------------
# Play Store collection settings
# ---------------------------------------------------------------------------
PLAY_STORE_LANG = "en"
PLAY_STORE_COUNTRY = "us"
PLAY_STORE_FETCH_COUNT = 3000  # fetch up to this many, then filter by date

# ---------------------------------------------------------------------------
# App Store collection settings
# ---------------------------------------------------------------------------
APP_STORE_HOW_MANY = 2000  # reviews to fetch per country

# ---------------------------------------------------------------------------
# Spotify Community forum
# ---------------------------------------------------------------------------
FORUM_BASE_URL = "https://community.spotify.com"
FORUM_BOARDS = [
    "/t5/Live-Ideas/idb-p/ideas_live",                 # live feature ideas / unmet needs
    "/t5/Ongoing-Issues/idb-p/ongoing_issues",         # reported issues / frustrations
    "/t5/Implemented-Ideas/idb-p/ideas_implemented",   # implemented ideas (context)
    "/t5/Closed-Ideas/idb-p/ideas_no",                 # declined ideas (unmet needs)
]
FORUM_PAGES_PER_BOARD = 10    # pages to scrape per board (20 threads/page typical)
FORUM_REQUEST_DELAY = 1.5     # seconds between forum requests (be polite)
FORUM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# LLM — llama-3.3-70b-versatile via Groq free tier
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

LLM_LIMITS = {
    "rpm": 30,       # requests per minute
    "rpd": 1000,     # requests per day
    "tpm": 12000,    # tokens per minute
    "tpd": 100000,   # tokens per day
}
LLM_SAFETY = 0.90            # use only 90% of each limit as a safety margin
BATCH_SIZE = 12              # reviews per LLM classification request
MAX_REVIEW_TOKENS = 60       # truncate each review to this many tokens before sending
SYNTHESIS_TOKEN_BUDGET = 10000  # tokens reserved per day for insight synthesis

# ---------------------------------------------------------------------------
# Theme classification keywords (Phase 3 — rule-based pass)
# ---------------------------------------------------------------------------
THEME_KEYWORDS: dict[str, list[str]] = {
    "DISCOVERY_PROBLEMS": [
        "find new", "discover", "hard to find", "same songs", "can't find",
        "not discovering", "new music", "explore", "finding music",
        "nothing new", "no new", "limited discovery",
    ],
    "RECOMMENDATION_FRUSTRATIONS": [
        "recommend", "algorithm", "suggestions", "repetitive", "same tracks",
        "keeps suggesting", "bad recommendations", "irrelevant", "not relevant",
        "doesn't understand", "wrong genre", "off", "recommendation engine",
    ],
    "LISTENING_GOALS": [
        "mood", "explore genre", "new artists", "playlist for", "want to listen",
        "looking for", "trying to find", "background music", "workout", "study",
        "focus", "relax", "party", "road trip",
    ],
    "REPEAT_LISTENING_CAUSES": [
        "keeps playing", "already know", "loop", "same stuff", "hear it again",
        "plays the same", "repeat", "same playlist", "always recommends",
        "stuck on", "only plays",
    ],
    "UNMET_NEEDS": [
        "wish", "should add", "need a", "feature request", "would be great",
        "please add", "missing", "lacks", "doesn't have", "want a feature",
        "suggestion", "improve", "could be better",
    ],
}

# ---------------------------------------------------------------------------
# Segmentation keywords (Phase 3 — rule-based)
# ---------------------------------------------------------------------------
SEGMENT_KEYWORDS: dict[str, list[str]] = {
    "Premium Users": ["premium", "paid", "subscription", "family plan", "student plan"],
    "Free Users": ["free tier", "free version", "ads", "shuffle only", "can't skip"],
    "Playlist Users": ["playlist", "my mixes", "made for you", "daily mix"],
    "Podcast Listeners": ["podcast", "episode", "show", "host", "listen to shows"],
    "Genre Explorers": ["genre", "explore", "new artists", "indie", "jazz", "classical"],
    "New Users": ["just downloaded", "new to spotify", "first time", "just started", "switched"],
    "Casual Listeners": ["background", "casual", "sometimes", "occasionally"],
    "Power Users": ["power user", "heavy user", "use it all day", "always on", "daily"],
}
