# Phase 6 — Deploy on Streamlit Community Cloud

Free hosting for the read-only dashboard. The pipeline (phases 1–4) runs locally or via GitHub Actions; the deployed app only reads `data/reviews.db`.

---

## Prerequisites

- GitHub account (free)
- [Streamlit Community Cloud](https://streamlit.io/cloud) account (free, sign in with GitHub)
- `data/reviews.db` committed to the repo (see `.gitignore` — the DB is tracked for deploy)
- Pipeline has been run at least once (`python run_all.py` or the weekly GitHub Action)

---

## Step 1 — Push the repo to GitHub

```powershell
cd d:\Projects\AIReviewEngine
git init
git add .
git commit -m "Initial commit: pipeline, dashboard, and weekly scheduler"
gh repo create AIReviewEngine --public --source=. --push
```

If the repo already exists:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/AIReviewEngine.git
git push -u origin main
```

Ensure these files are in the commit:

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Streamlit Cloud entry point |
| `dashboard/app.py` | Dashboard implementation |
| `data/reviews.db` | SQLite data for the live app |
| `requirements.txt` | Python dependencies |
| `.streamlit/config.toml` | Dark theme defaults |

---

## Step 2 — Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app**.
3. Select your repository and branch (`main`).
4. Set **Main file path** to:
   ```
   streamlit_app.py
   ```
   (Alternatively: `dashboard/app.py`)
5. Click **Deploy**.

No environment secrets are required for the dashboard — it is read-only and does not call Groq at runtime.

---

## Step 3 — Verify the live app

After the build completes (~2–5 minutes):

- Header shows **Spotify** branding and **AI-Powered Review Discovery Engine**
- KPI cards show review counts
- Theme Frequency, Segment Snapshot, and Top 10 Opportunities render
- Review Explorer filters work

If you see *"Database not found"*:

- Confirm `data/reviews.db` is in the GitHub repo (not gitignored)
- Reboot the app from the Streamlit Cloud manage screen after pushing the DB

---

## Step 4 — Keep data fresh (weekly)

Use the GitHub Actions scheduler (`.github/workflows/weekly-pipeline.yml`):

1. Add repository secrets: `GROQ_API_KEY` (required).
2. The workflow runs every **Monday 02:00 UTC** (or trigger manually from Actions).
3. It runs phases 1–4 and commits an updated `data/reviews.db`.
4. Streamlit Cloud picks up the new commit — use **Reboot app** or wait for auto-redeploy.

During the LLM backlog, trigger the workflow manually every few days until `UNCLASSIFIED` is low. See `docs/llmRerunPlan.md`.

---

## Local deploy readiness check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate-streamlit-deploy.ps1
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on `requirements.txt` | Check Streamlit Cloud logs; ensure `pip install -r requirements.txt` works locally |
| Empty dashboard | Push `data/reviews.db`; run phase 4 first |
| Stale data after weekly run | Reboot app on Streamlit Cloud after GitHub Action commits |
| App works locally but not on Cloud | Use `streamlit_app.py` as entry point; confirm Python 3.11 |

---

## Architecture summary

```
GitHub Actions (weekly)  →  updates data/reviews.db  →  commit to GitHub
                                                              ↓
                                              Streamlit Community Cloud
                                              (reads reviews.db, no API keys)
```

No paid database, API subscription, or separate backend is required.
