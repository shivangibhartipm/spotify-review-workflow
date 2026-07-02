# Project Decisions

Finalized decisions from implementation. Brainstorming and reversed approaches are not listed here.

---

## Architecture & stack

- **Pipeline shape:** linear phases — Collect → Clean → Enrich → Insights → Dashboard.
- **Storage:** single SQLite file (`data/reviews.db`) with separate tables per phase (`raw_reviews`, `clean_reviews`, `enriched_reviews`, `insights`, `llm_cache`, `llm_usage`).
- **Orchestration:** `run_all.py` with `--phase 1|2|3|4`; each phase is idempotent and can be re-run independently.
- **Dashboard:** one Streamlit app (`dashboard/app.py`) with four tabs, reading from SQLite.
- **Cost constraint:** free tooling only — free scrapers, Groq free tier, local SQLite, optional Streamlit Community Cloud deploy.

---

## LLM

- **Model:** `llama-3.3-70b-versatile` via **Groq API** (free tier).
- **Limits (Groq free tier):** 30 RPM, 1,000 RPD, 12,000 TPM, 100,000 TPD.
- **Usage strategy:** LLM is the exception, not the default.
  - Sentiment, topics, and segments use classical NLP / rules only (no LLM).
  - Theme classification: **rules first**; LLM only for low-confidence / ambiguous reviews.
  - Batched calls (~12 reviews per request), aggressive SQLite caching (`llm_cache`), 90% safety margin on limits.
- **Rate limiting:** custom `LLMRateLimiter` enforces RPM/TPM/RPD/TPD; stops cleanly when daily budget is exhausted; no retry storms on limit errors.
- **Phase 4 insight synthesis:** skipped for MVP — deterministic summaries only (LLM synthesis deferred to avoid burning token budget).

---

## Data collection (Phase 1)

- **Window:** last ~90 days, enforced by publish/post date per source.
- **Play Store:** `google-play-scraper`, newest-first until outside window.
- **App Store:** direct **iTunes RSS API** (not `app-store-scraper` — unreliable on this environment).
- **Forums:** Spotify Community via **Khoros v1 REST API** (`/restapi/vc/boards/id/{board}/topics`); topic subject + teaser from listing pages only (no per-thread fetches).
- **Forum boards:** `ideas_live`, `ongoing_issues`, `ideas_no`, `ideas_implemented`.
- **IDs:** `source:native_id`; insert with `INSERT OR IGNORE` for idempotency.
- **Windows SSL:** `truststore` injects OS certificate store (handles corporate proxy SSL).

---

## Data cleaning (Phase 2)

- **Single module:** `src/clean/pipeline.py` (no subphase split).
- **Steps:** deduplicate (normalized hash), remove URLs/emojis, normalize text, `langdetect`, keep English-only → `clean_reviews`.
- **Rebuild:** full table rebuild on each run so rule changes apply cleanly.

---

## Enrichment (Phase 3)

- **3a Sentiment:** VADER (`positive` ≥ 0.05, `negative` ≤ −0.05, else `neutral`).
- **3b Topics:** scikit-learn `TfidfVectorizer` + NMF (~10 topics), human-readable labels from top keywords.
- **3c Themes:** hybrid rules (`THEME_KEYWORDS` in `config.py`) + batched Groq LLM for low-confidence only; `UNCLASSIFIED` when LLM unavailable or budget exhausted.
- **3d Segments:** rule-based keyword matching → JSON list with confidence.
- **Rebuild:** `enriched_reviews` fully rebuilt each run.

---

## Insights (Phase 4)

- **Module:** `src/insights/build_insights.py`.
- **Aggregates:** discovery problems, frustrations, listening goals, repeat causes, opportunities, segments, segment×theme, sentiment.
- **Per row:** `insight_type`, `label`, `count`, `example_ids` (JSON), deterministic `summary`.
- **Export:** optional CSV snapshot to `data/exports/insights.csv`.

---

## Dashboard (Phase 5)

- **Tabs:** Overview, Pain Points, Segments & Behavior, Opportunities & Explorer.
- **Data sources:** `enriched_reviews` + `clean_reviews` for drill-down; `insights` for precomputed top lists.
- **Review Explorer:** sidebar filters (source, sentiment, theme, topic, segment, date); full review drill-down by ID.

---

## Operational notes

- **Re-run Phase 3 daily** to classify remaining low-confidence themes as Groq budget allows; cached prompts cost zero tokens.
- **Social media** (X/Instagram/TikTok): not implemented — no reliable free access; architecture does not depend on it.
