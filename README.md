# AI-Powered Review Discovery Engine

Turns Spotify user reviews from the last 90 days into structured product insights — theme classification, sentiment, user segments, and a Streamlit dashboard — using `llama-3.3-70b-versatile` on Groq's free tier.

## Quick start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up credentials
```bash
cp .env.example .env
# Edit .env and fill in GROQ_API_KEY
```

- **Groq API key** (free): https://console.groq.com

### 3. Run the pipeline

Run all phases in order:
```bash
python run_all.py
```

Or run individual phases:
```bash
python run_all.py --phase 1   # collect reviews
python run_all.py --phase 2   # clean reviews
python run_all.py --phase 3   # enrich (sentiment, topics, themes, segments)
python run_all.py --phase 4   # build insights
```

### 4. Launch the dashboard
```bash
streamlit run dashboard/app.py
```

---

## Project structure

```
AIReviewEngine/
├── docs/                     # problem statement and architecture
├── data/
│   ├── reviews.db            # SQLite database (all pipeline tables)
│   └── exports/              # optional CSV snapshots
├── src/
│   ├── config.py             # all settings in one place
│   ├── db.py                 # SQLite helpers
│   ├── collect/              # Phase 1 — data collection
│   ├── clean/                # Phase 2 — cleaning pipeline
│   ├── enrich/               # Phase 3 — sentiment, topics, themes, segments
│   ├── llm/                  # Groq LLM client, rate limiter, cache
│   └── insights/             # Phase 4 — insight aggregation
├── dashboard/
│   └── app.py                # Streamlit dashboard (Phase 5)
├── run_all.py                # pipeline orchestrator
├── requirements.txt
└── .env.example
```

## Data sources

| Source | What is collected |
|--------|-------------------|
| Google Play Store | Android reviews for Spotify (last 90 days) |
| Apple App Store | iOS reviews for Spotify (last 90 days) |
| Spotify Community forums | Threads from the Ideas and Music boards |

## Re-running safely

Every phase is **idempotent** — re-running inserts only new rows (`INSERT OR IGNORE`). Run the pipeline weekly to keep the 90-day window fresh without duplicating data.

LLM calls are **cached** in the `llm_cache` table — re-runs never re-spend tokens on already-processed reviews.

## Weekly automation (GitHub Actions)

A scheduled workflow runs phases 1–4 every **Sunday 10:00 AM IST** and commits updated `data/reviews.db` and `data/exports/insights.csv`.

1. Add GitHub Actions secret: `GROQ_API_KEY` (required).
2. Push the repo and run **Weekly pipeline refresh** manually once from the Actions tab.
3. Deploy the dashboard on Streamlit Community Cloud pointing at `streamlit_app.py`.

See **`docs/deploy.md`** for Phase 6 deployment steps and `docs/llmRerunPlan.md` for daily LLM catch-up runs.
