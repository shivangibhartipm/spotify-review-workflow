# LLM Re-run Plan — Daily Theme Classification

This plan covers how to finish theme classification for reviews that are still `UNCLASSIFIED` after hitting the Groq free-tier daily limit.

---

## Current status (as of 2 Jul 2026)

| Metric | Value |
|--------|------:|
| Total enriched reviews | 5,062 |
| Still `UNCLASSIFIED` | **2,680** |
| Classified (rules + LLM) | 2,382 |
| LLM cache entries | 138 batches |
| Today's LLM usage | 54 requests · 64,970 tokens |

**Estimated time to clear backlog:** ~3–4 more daily runs (tokens are the bottleneck, not request count).

---

## Why daily re-runs are needed

Phase 3 uses a **hybrid** theme classifier:

1. **Rules first** — ~670 reviews are classified confidently without LLM.
2. **LLM for low-confidence only** — ~4,392 reviews are batched (12 per request) and sent to Groq.
3. **Daily stop** — when the token budget is exhausted, Phase 3 stops cleanly and leaves remaining reviews as `UNCLASSIFIED`.
4. **Cache resume** — already-classified batches are stored in `llm_cache` and cost **zero tokens** on the next run.

Re-running Phase 3 each day picks up where the previous run left off. No manual reset is required.

---

## Tomorrow's run (3 Jul 2026)

Run this **once per day**, preferably after the Groq daily quota resets (UTC midnight).

### 1. Check backlog before starting

```powershell
cd d:\Projects\AIReviewEngine
python -c "
import sqlite3
conn = sqlite3.connect('data/reviews.db')
total = conn.execute('select count(*) from enriched_reviews').fetchone()[0]
unclass = conn.execute(\"select count(*) from enriched_reviews where theme='UNCLASSIFIED'\").fetchone()[0]
cache = conn.execute('select count(*) from llm_cache').fetchone()[0]
usage = conn.execute(\"select requests, tokens from llm_usage where day=date('now')\").fetchone()
print(f'Enriched: {total:,}  |  UNCLASSIFIED: {unclass:,}  |  Cache batches: {cache}')
print(f'Today LLM usage so far: {usage[0] if usage else 0} requests, {usage[1] if usage else 0} tokens')
"
```

Confirm `UNCLASSIFIED` is still > 0 and today's usage is **0** (fresh quota).

### 2. Re-run Phase 3 (enrichment + LLM themes)

```powershell
python run_all.py --phase 3
```

**Expected behaviour:**

- Sentiment, topics, and segments recompute quickly (no LLM).
- Theme LLM pass processes batches until the daily limit is hit.
- Log messages like `Theme LLM pass stopped: daily limit reached` are **normal** — not an error.
- `UNCLASSIFIED` count should drop compared to yesterday.

**Do not:**

- Re-run Phase 3 multiple times on the same day (wastes quota on duplicate work).
- Add retry loops or force `--phase 3` in a tight loop.

### 3. Re-run Phase 4 (refresh dashboard insights)

```powershell
python run_all.py --phase 4
```

This rebuilds the `insights` table and `data/exports/insights.csv` so the Streamlit dashboard reflects newly classified themes and updated opportunity rankings.

### 4. Verify progress after the run

```powershell
python -c "
import sqlite3
conn = sqlite3.connect('data/reviews.db')
unclass = conn.execute(\"select count(*) from enriched_reviews where theme='UNCLASSIFIED'\").fetchone()[0]
by_theme = conn.execute('select theme, count(*) c from enriched_reviews group by theme order by c desc').fetchall()
usage = conn.execute(\"select requests, tokens from llm_usage where day=date('now')\").fetchone()
print(f'UNCLASSIFIED remaining: {unclass:,}')
print(f'Today LLM usage: {usage[0]} requests, {usage[1]} tokens')
print('Theme breakdown:')
for theme, count in by_theme:
    print(f'  {theme}: {count:,}')
"
```

### 5. Refresh the dashboard

```powershell
streamlit run dashboard/app.py
```

Check that Theme Frequency, Segment Snapshot, and Top 10 Opportunities look more complete than yesterday.

---

## Daily schedule (next 3–4 days)

| Day | Action | Target |
|-----|--------|--------|
| **3 Jul** (tomorrow) | Phase 3 → Phase 4 | `UNCLASSIFIED` drops from ~2,680 toward ~2,000 |
| **4 Jul** | Phase 3 → Phase 4 | `UNCLASSIFIED` ~1,200–1,500 |
| **5 Jul** | Phase 3 → Phase 4 | `UNCLASSIFIED` ~400–800 |
| **6 Jul** | Phase 3 → Phase 4 | `UNCLASSIFIED` near 0 (or accept residual generic reviews) |

> Exact counts depend on how many reviews fit in each batch and how fast token budget is consumed (~50–80 batches/day).

---

## When to stop daily runs

Switch back to **weekly** runs when **any** of these is true:

- `UNCLASSIFIED` is below **100** (residual reviews are likely generic app feedback with no clear theme).
- `UNCLASSIFIED` stops decreasing for **2 consecutive days** (remaining reviews may not benefit from more LLM passes).
- You are satisfied with dashboard quality for demo/deployment.

After that, use the **weekly GitHub Actions scheduler** (`.github/workflows/weekly-pipeline.yml`) instead of manual daily runs.

---

## GitHub Actions weekly scheduler

Workflow file: `.github/workflows/weekly-pipeline.yml`

| Trigger | When |
|---------|------|
| **Schedule** | Every Sunday at 10:00 AM IST (04:30 UTC) |
| **Manual** | Actions tab → *Weekly pipeline refresh* → *Run workflow* |

### What it does

1. Installs Python dependencies
2. Runs `python run_all.py` (phases 1–4)
3. Prints enriched / `UNCLASSIFIED` / insight counts
4. Commits `data/reviews.db` and `data/exports/insights.csv` back to the repo

Streamlit Community Cloud can then read the latest committed database on redeploy.

### One-time GitHub setup

1. Push this repo to GitHub.
2. Add repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | Required | Notes |
|--------|----------|-------|
| `GROQ_API_KEY` | Yes | Groq free-tier key for theme LLM |

3. Ensure `data/reviews.db` is tracked in git (it is no longer gitignored).
4. Trigger a manual run once to verify the workflow before relying on the Sunday schedule.

### During the LLM backlog (optional)

While `UNCLASSIFIED` is still high, you can **manually trigger** the workflow daily from the Actions tab. After the backlog clears, rely on the weekly schedule only.

> **Note:** Groq's daily token limit applies per calendar day (UTC). A single workflow run will classify as many batches as one day's quota allows; remaining reviews are picked up on the next manual or weekly run.

---

## Groq limits reference

| Limit | Groq free tier | Pipeline cap (90% safety) |
|-------|---------------:|--------------------------:|
| Requests/day | 1,000 | 900 |
| Tokens/day | 100,000 | 90,000 |
| Requests/min | 30 | 27 |
| Tokens/min | 12,000 | 10,800 |

**Bottleneck:** tokens/day (~1,100 tokens per batch on recent runs).

---

## Prerequisites

- `.env` contains a valid `GROQ_API_KEY`.
- `data/reviews.db` exists with Phase 2 output (`clean_reviews` populated).
- Run from project root: `d:\Projects\AIReviewEngine`.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Phase 3 finishes in seconds, `UNCLASSIFIED` unchanged | Daily quota already used today | Wait until tomorrow (UTC reset) |
| `Theme LLM pass skipped; GROQ_API_KEY` | Missing API key | Add key to `.env` |
| `UNCLASSIFIED` barely moves | Most batches already cached; few new reviews per day | Normal near end of backlog |
| Groq 429 before internal ledger hits 90% | Groq hard limit vs internal estimate mismatch | Stop for the day; resume tomorrow |

---

## Quick reference — one-liner for tomorrow

```powershell
cd d:\Projects\AIReviewEngine; python run_all.py --phase 3; python run_all.py --phase 4
```

Then verify `UNCLASSIFIED` dropped and launch the dashboard.
