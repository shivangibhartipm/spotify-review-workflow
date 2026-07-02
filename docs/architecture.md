# Architecture — AI-Powered Review Discovery Engine

This document describes a **phase-wise architecture** for building the review intelligence system defined in [`problemStatement.md`](./problemStatement.md).

Design goals:

- **100% free tooling** — no paid APIs, no paid hosting.
- **Free LLM** — `llama-3.3-70b-versatile` via **Groq's free tier**, used carefully within strict rate limits.
- **Simple, easy-to-build dashboard** — one Streamlit app, no separate frontend/backend.
- **Local-first** — everything runs on a laptop; optional free cloud deploy at the end.
- **Reproducible** — plain Python scripts run in order, data flows through clear stages.

> **LLM budget is the tightest constraint in this project.** Groq's free tier for `llama-3.3-70b-versatile` allows only **30 requests/min, 1,000 requests/day, 12,000 tokens/min, and 100,000 tokens/day**. The entire architecture is designed so classical NLP does the bulk of the work and the LLM is used **selectively, in batches, and with aggressive caching** so these limits are never hit. See [Section 5 — LLM strategy & rate-limit budget](#5-llm-strategy--rate-limit-budget).

---

## 1. High-level overview

The system is a linear pipeline. Each phase reads the previous phase's output and writes its own, so any stage can be re-run independently.

```
[Collect]  ->  [Clean]  ->  [Enrich: topics + themes + sentiment + segments]  ->  [Insights]  ->  [Dashboard]
   raw.db        clean.db              enriched.db                                 insights.db      Streamlit
```

All stages share one SQLite database file with different tables, so there is no server to run.

---

## 2. Technology choices (all free)

| Concern | Tool | Why |
|---------|------|-----|
| Language | Python 3.11+ | Rich free ecosystem for scraping + NLP |
| App Store scraping | `app-store-scraper` | Free, no API key |
| Play Store scraping | `google-play-scraper` | Free, no API key |
| Forums | `requests` + Khoros API | Spotify Community forum threads |
| Storage | **SQLite** (built into Python) | Zero setup, single file, SQL queries |
| Data wrangling | `pandas` | Standard, free |
| Language detect | `langdetect` or `fasttext-langdetect` | Free, offline |
| Text cleaning | `nltk`, `re`, `emoji` | Free stopwords + regex |
| Sentiment | `vaderSentiment` | Free, offline, no model download pain |
| Topic modeling | `scikit-learn` (LDA/NMF) or `BERTopic` | Both free; start with scikit-learn |
| Theme classification | Rule-based keywords **first**, LLM only for low-confidence cases | Keeps LLM calls small (see Section 5) |
| Segmentation | Rule-based keyword matching | Free, transparent, easy to tune |
| **LLM** | **`llama-3.3-70b-versatile` via Groq API** | Free tier; used for ambiguous classification + insight synthesis |
| LLM client | `groq` Python SDK | Official free SDK |
| Rate limiting / retries | `tenacity` + custom token-bucket | Enforces RPM/RPD/TPM/TPD limits |
| Dashboard | **Streamlit** + Plotly | Simplest way to build a data dashboard in Python |
| Deployment (optional) | **Streamlit Community Cloud** | Free public hosting |
| Orchestration | `python` scripts + `Makefile` / batch file | No Airflow needed |

> Note on social media: X/Instagram/TikTok/Reddit have restrictive or credential-heavy free access. The MVP collects app stores and Spotify Community forums reliably; social sources are out of scope.

---

## 3. Project structure

```
AIReviewEngine/
├── docs/
│   ├── problemStatement.md
│   └── architecture.md
├── data/
│   ├── reviews.db            # single SQLite file, all tables
│   └── exports/              # optional CSV snapshots
├── src/
│   ├── config.py             # sources, date window, keywords, DB path, LLM limits
│   ├── collect/
│   │   ├── app_store.py
│   │   ├── play_store.py
│   │   └── forums.py
│   ├── clean/
│   │   └── pipeline.py
│   ├── enrich/
│   │   ├── sentiment.py
│   │   ├── topics.py
│   │   ├── themes.py
│   │   └── segments.py
│   ├── llm/
│   │   ├── client.py         # Groq client wrapper
│   │   ├── rate_limiter.py   # token-bucket for RPM/RPD/TPM/TPD
│   │   ├── cache.py          # SQLite-backed prompt/response cache
│   │   └── prompts.py        # batched classification + synthesis prompts
│   ├── insights/
│   │   └── build_insights.py
│   └── db.py                 # SQLite helpers (connect, upsert, read)
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── .env                      # GROQ_API_KEY (never committed)
├── requirements.txt
├── run_all.py                # runs phases 1..4 in order
└── README.md
```

---

## 4. Data model (SQLite tables)

One database file, `data/reviews.db`.

**`raw_reviews`** — untouched ingested data

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (PK) | `source:native_id` to guarantee uniqueness |
| source | TEXT | app_store / play_store / forum |
| text | TEXT | original text |
| rating | INTEGER | nullable |
| date | TEXT (ISO) | publish/post date |
| url | TEXT | original link or ID |
| collected_at | TEXT | ingestion timestamp |

**`clean_reviews`** — after cleaning (English-only, deduped)

| Column | Type |
|--------|------|
| id | TEXT (PK, FK to raw) |
| clean_text | TEXT |
| language | TEXT |
| source, rating, date, url | (carried over) |

**`enriched_reviews`** — analysis columns joined onto clean rows

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (PK) |
| sentiment | TEXT | positive / neutral / negative |
| sentiment_score | REAL | -1..1 |
| topic_label | TEXT | from topic model |
| topic_confidence | REAL | 0..1 |
| theme | TEXT | DISCOVERY_PROBLEMS, etc. |
| segments | TEXT | JSON list of {segment, confidence} |

**`insights`** — precomputed aggregates for the dashboard

| Column | Type | Notes |
|--------|------|-------|
| insight_type | TEXT | discovery_problem / frustration / opportunity / listening_goal |
| label | TEXT | e.g. "Repetitive recommendations" |
| count | INTEGER | supporting review count |
| example_ids | TEXT | JSON list of review ids for excerpts |
| summary | TEXT | optional LLM-generated one-line summary |

**`llm_cache`** — makes LLM calls idempotent and re-runs free

| Column | Type | Notes |
|--------|------|-------|
| prompt_hash | TEXT (PK) | SHA-256 of (model + prompt) |
| response | TEXT | raw JSON/text returned |
| created_at | TEXT | timestamp |

**`llm_usage`** — running ledger to enforce daily limits across runs

| Column | Type | Notes |
|--------|------|-------|
| day | TEXT (PK) | YYYY-MM-DD |
| requests | INTEGER | requests used today |
| tokens | INTEGER | tokens used today |

The dashboard reads mostly from `insights` (fast) and `enriched_reviews` (for the Review Explorer).

---

## 5. LLM strategy & rate-limit budget

The LLM (`llama-3.3-70b-versatile` on Groq's free tier) is powerful but **rate-limited**. Getting this right is the make-or-break design decision, so the whole pipeline treats LLM calls as a scarce resource.

### 5.1 The limits

| Limit | Value |
|-------|-------|
| Requests / minute (RPM) | 30 |
| Requests / day (RPD) | 1,000 |
| Tokens / minute (TPM) | 12,000 |
| Tokens / day (TPD) | 100,000 |

**The binding constraint is tokens/day (100K).** If we naïvely sent one request per review with a full prompt (~300–500 tokens each), we'd exhaust the daily budget after only ~200–300 reviews. So we do three things: **(1) only call the LLM when rules are not confident, (2) batch many reviews per request, and (3) cache every response.**

### 5.2 Core principle — LLM is the exception, not the default

```
Rule-based / classical NLP  ->  handles ~60–80% of reviews (free, instant)
                LLM         ->  handles only low-confidence / ambiguous reviews + a few synthesis calls
```

- **Sentiment, topics, segmentation** never call the LLM — VADER + scikit-learn + keyword rules cover them.
- **Theme classification** calls the LLM only for reviews the keyword rules can't confidently label.
- **Insight synthesis** (short human-readable summaries) uses a small, fixed number of calls at the very end.

### 5.3 Batching (the key to staying under budget)

Instead of one review per request, pack **10–15 short reviews into a single request** and ask for a compact JSON array back.

- Prompt overhead (instructions + theme list): ~200 tokens, shared across the whole batch.
- Each review: truncate to ~60 tokens of cleaned text.
- Output: compact JSON like `[{"i":1,"theme":"DISCOVERY_PROBLEMS"}...]`, ~10 tokens/review.

**Approximate cost per batch of 12 reviews:** ~200 + (12 × 60) + (12 × 10) ≈ **1,040 tokens for 12 reviews ≈ ~87 tokens/review** (vs. ~400+ tokens/review unbatched — a ~4–5× saving).

### 5.4 Daily throughput under the budget

Reserve ~10K tokens/day for insight synthesis, leaving ~90K/day for classification:

| Metric | Estimate |
|--------|----------|
| Tokens/day for classification | ~90,000 |
| Tokens per batch (12 reviews) | ~1,040 |
| Batches/day | ~86 |
| **Reviews classified by LLM / day** | **~1,000** |
| Requests/day used | ~86 + synthesis (well under 1,000 RPD) |

Because only low-confidence reviews go to the LLM, a corpus of a few thousand reviews is fully processed in **1–3 daily runs**. Already-cached reviews cost **zero** tokens on later runs.

### 5.5 Rate limiter (`src/llm/rate_limiter.py`)

A small token-bucket that enforces **all four limits** before every call:

- Tracks a rolling 60-second window for **RPM** and **TPM**.
- Reads/writes the `llm_usage` table for **RPD** and **TPD** (survives restarts).
- Estimates a request's token cost *before* sending; if it would breach TPM, it `sleep()`s until the window frees up; if it would breach TPD/RPD, it **stops cleanly** and the pipeline resumes the next day.
- Wrap the actual API call with `tenacity` for exponential backoff on `429` responses (belt-and-suspenders).

```python
# conceptual guard around every call
limiter.reserve(estimated_tokens)   # blocks or raises DailyLimitReached
resp = groq_call(...)
limiter.record(actual_tokens=resp.usage.total_tokens)
```

### 5.6 Caching (`src/llm/cache.py`)

- Key every call by `sha256(model + prompt)`.
- Before calling: look up `llm_cache`; on hit, return stored response (0 tokens).
- After calling: store the response.
- Effect: re-running the pipeline, tweaking the dashboard, or resuming after a daily-limit stop never re-spends budget on already-processed reviews.

### 5.7 Config (`src/config.py`)

```python
GROQ_MODEL = "llama-3.3-70b-versatile"
LLM_LIMITS = {"rpm": 30, "rpd": 1000, "tpm": 12000, "tpd": 100000}
LLM_SAFETY = 0.9              # use only 90% of each limit as a safety margin
BATCH_SIZE = 12              # reviews per classification request
MAX_REVIEW_TOKENS = 60       # truncate each review before sending
SYNTHESIS_TOKEN_BUDGET = 10000
# GROQ_API_KEY is read from .env, never hard-coded
```

---

## Phase 1 — Data collection (last ~90 days)

**Goal:** pull recent reviews into `raw_reviews`, keeping source metadata.

**Steps**

1. Define the window in `config.py`: `START_DATE = today - 90 days`.
2. For each source, fetch newest-first and stop once records fall before `START_DATE`.
   - App Store: `app_store_scraper` by app id/country.
   - Play Store: `google_play_scraper` `reviews()` with `count` + `sort=NEWEST`.
   - Forums: Khoros API on Spotify Community boards.
3. Build a stable `id` = `source:native_id`; insert with `INSERT OR IGNORE` for idempotency.

**Free-tier tips**

- Add polite delays (`time.sleep`) and a user-agent for scraping.
- Cache raw pulls so re-runs don't refetch.

**Output:** `raw_reviews` populated, all dated within ~90 days.

---

## Phase 2 — Data cleaning

**Goal:** produce `clean_reviews` (English-only, deduplicated, normalized).

**Pipeline (`src/clean/pipeline.py`)**

| Step | How |
|------|-----|
| Deduplicate | Drop exact/near-duplicate text (normalized hash) within and across sources |
| Remove URLs | Regex `https?://\S+` |
| Remove emojis | `emoji.replace_emoji` |
| Stopwords | `nltk` English stopword list |
| Normalize | lowercase, strip, collapse whitespace, standardize punctuation |
| Detect language | `langdetect` |
| Filter | keep rows where language == `en` |

Keep an unstopworded copy of text for display, and a stopword-removed copy for modeling if desired. Write results to `clean_reviews` (raw table stays intact).

**Output:** `clean_reviews`.

---

## Phase 3 — Enrichment (topics, themes, sentiment, segments)

Each sub-step reads `clean_reviews` and writes/updates `enriched_reviews`. Run in any order except themes may reuse topic output.

### 3a. Sentiment (`sentiment.py`)
- `vaderSentiment` compound score → map to positive (≥0.05), negative (≤-0.05), neutral otherwise.

### 3b. Topic modeling (`topics.py`)
- Start simple: `TfidfVectorizer` + `NMF` (or `LatentDirichletAllocation`) from scikit-learn.
- Pick ~8–12 topics; label the top keywords per topic to human-readable names (Music Discovery, Recommendations, Search, Playlists, etc.).
- Store `topic_label` and `topic_confidence` (document-topic weight).
- Optional upgrade: `BERTopic` for better topics (still free).

### 3c. Theme classification (`themes.py`) — hybrid rules + LLM
This is the **only per-review step that uses the LLM**, and only for the reviews rules can't handle.

**Step 1 — rules first (free, covers most reviews).** Score each review against keyword dictionaries; if one theme clearly wins, assign it and skip the LLM.

```python
THEME_KEYWORDS = {
    "DISCOVERY_PROBLEMS": ["find new", "discover", "hard to find", "same songs"],
    "RECOMMENDATION_FRUSTRATIONS": ["recommend", "algorithm", "suggestions", "repetitive"],
    "LISTENING_GOALS": ["mood", "explore genre", "new artists", "playlist for"],
    "REPEAT_LISTENING_CAUSES": ["keeps playing", "already know", "loop", "same stuff"],
    "UNMET_NEEDS": ["wish", "should add", "need a", "feature request"],
}
```

**Step 2 — LLM only for low-confidence reviews.** Reviews with no clear keyword winner (ambiguous, mixed, or novel wording) are collected and sent to `llama-3.3-70b-versatile` **in batches of ~12** (see Section 5.3). The prompt sends the theme list once plus the numbered reviews, and asks for a compact JSON array of `{index, theme, confidence}`.

- Every batch goes through the **rate limiter** (Section 5.5) and **cache** (Section 5.6), so limits are never breached and re-runs are free.
- If the daily token/request budget is reached, the step stops cleanly; unprocessed reviews keep their rule-based best-guess (or `UNCLASSIFIED`) and are finished on the next daily run.
- Store the resulting `theme`; keep topic tags as supporting context.

This hybrid keeps ~60–80% of reviews off the LLM entirely, so a few thousand reviews fit comfortably within the free-tier daily budget.

### 3d. Segmentation (`segments.py`)
- Rule-based keyword matching → JSON list with confidence.

```python
SEGMENT_KEYWORDS = {
    "Premium Users": ["premium", "paid", "subscription"],
    "Free Users": ["free tier", "ads", "shuffle only"],
    "Playlist Users": ["playlist", "my mixes"],
    "Podcast Listeners": ["podcast", "episode"],
    "Genre Explorers": ["genre", "explore", "new artists"],
    "New Users": ["just downloaded", "new to spotify", "first time"],
}
```

**Output:** `enriched_reviews` fully populated.

---

## Phase 4 — Insight extraction

**Goal:** precompute the aggregates the dashboard needs into `insights`.

**`build_insights.py`**

- Group `enriched_reviews` by theme, topic, segment, sentiment.
- Compute counts for: top discovery problems, top recommendation frustrations, listening goals, top opportunities (from `UNMET_NEEDS` clusters).
- For each aggregate, store a few `example_ids` for representative excerpts.
- Save to `insights` table (and optionally CSVs in `data/exports/`).

Doing aggregation here keeps the dashboard fast and simple (it just reads rows).

**Optional LLM synthesis (small, fixed budget).** After aggregation, make a **handful** of LLM calls (not per-review) to turn the top clusters into short, PM-friendly summaries — e.g. one call that takes the top ~10 opportunity clusters (label + counts + a couple of example snippets) and returns a one-line summary each, written to `insights.summary`.

- This is capped by `SYNTHESIS_TOKEN_BUDGET` (~10K tokens/day, Section 5.7) and runs through the same rate limiter + cache.
- Typically only **2–5 requests total**, so it barely touches the RPD/TPD budget.
- Fully optional: if skipped, the dashboard shows counts + excerpts without generated summaries.

**Output:** `insights` table.

---

## Phase 5 — Dashboard (Streamlit)

**Goal:** one simple app (`dashboard/app.py`) with four tabs, reading from SQLite.

Run locally:

```bash
streamlit run dashboard/app.py
```

**Tabs**

1. **Overview**
   - Metric cards: total reviews, positive/neutral/negative, discovery-problem count, frustration count.
   - Plotly pie (sentiment) + bar (reviews by source).

2. **Pain Points**
   - Tables + bar charts: top discovery problems, top recommendation frustrations.
   - 3–5 excerpts per category (pulled via `example_ids`).

3. **Segments & Behavior**
   - Listening-goal counts (bar).
   - Segment summary table (review count, discovery problems, recommendation problems) + bar of problems by segment.

4. **Opportunities & Explorer**
   - Ranked opportunities with supporting counts.
   - **Review Explorer**: `st.dataframe` with filters (topic, theme, sentiment, segment, date, source); row selection shows full text + metadata.

**Why Streamlit:** pure Python, no HTML/JS, charts in a few lines, `@st.cache_data` makes it fast, and it deploys free.

---

## Phase 6 — (Optional) Deploy for free

1. Push the repo to a **free GitHub** account.
2. Commit a recent `data/reviews.db` (and `data/exports/insights.csv`) so the app has data.
3. Deploy on **Streamlit Community Cloud** (free): main file `streamlit_app.py` (or `dashboard/app.py`).
4. Refresh data via the **weekly GitHub Actions** workflow (`.github/workflows/weekly-pipeline.yml`), which commits an updated DB; reboot or redeploy the Streamlit app after each refresh.

See **`docs/deploy.md`** for step-by-step instructions.

No paid hosting, database server, or API subscription is required.

---

## 7. Orchestration & re-runs

`run_all.py` executes phases in order:

```python
# pseudocode
collect.run()      # Phase 1 -> raw_reviews
clean.run()        # Phase 2 -> clean_reviews
enrich.run()       # Phase 3 -> enriched_reviews
insights.run()     # Phase 4 -> insights
print("Done. Launch: streamlit run dashboard/app.py")
```

Each phase is idempotent (`INSERT OR IGNORE` / upsert on `id`), so you can re-run collection weekly to keep the 90-day window fresh without duplicating data.

**Daily-limit awareness:** the enrichment phase may stop early once the LLM daily budget (RPD/TPD) is reached. That is expected and safe — thanks to the `llm_cache` and `llm_usage` ledger, simply re-running `run_all.py` the next day resumes exactly where it left off without re-spending tokens on already-classified reviews. For small corpora this never triggers; for larger ones it spreads work across a few days at zero cost.

---

## 8. Suggested build order

1. Repo skeleton + `requirements.txt` + `config.py` + `db.py`.
2. Phase 1 for **one** source (Play Store is easiest) end-to-end.
3. Phase 2 cleaning on that data.
4. Dashboard Overview tab (prove the pipeline is visible early).
5. Add remaining collectors (App Store, forums).
6. Phase 3 enrichment — **rules only first** (sentiment → segments → topics → rule-based themes). Confirm the pipeline works end-to-end with **zero** LLM calls.
7. Add the LLM layer: `src/llm/` (client + cache + rate limiter), then wire it into theme classification for low-confidence reviews. Test on a tiny batch and watch the `llm_usage` ledger before scaling up.
8. Phase 4 insights (+ optional LLM synthesis) + remaining dashboard tabs.
9. Optional Phase 6 deploy.

This gives a working vertical slice fast, keeps the LLM out of the critical path until everything else works, then layers it in safely.

---

## 9. requirements.txt (starter)

```
app-store-scraper
google-play-scraper
requests
beautifulsoup4
pandas
langdetect
nltk
emoji
vaderSentiment
scikit-learn
groq
tenacity
python-dotenv
streamlit
plotly
```

- `groq` — free LLM client for `llama-3.3-70b-versatile`.
- `tenacity` — retry/backoff on rate-limit (`429`) responses.
- `python-dotenv` — load `GROQ_API_KEY` from `.env`.

Add `bertopic` only if you choose the optional topic-modeling upgrade.

---

## 10. Getting a free Groq API key

1. Sign up at [console.groq.com](https://console.groq.com) (free, no card required).
2. Create an API key.
3. Put it in `.env` as `GROQ_API_KEY=...` and add `.env` to `.gitignore`.
4. The free tier includes `llama-3.3-70b-versatile` at the limits in Section 5.1.
