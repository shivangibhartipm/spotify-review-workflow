# Local test for .github/workflows/weekly-pipeline.yml
# Mirrors the GitHub Actions job without git push.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> [1/4] Install dependencies (skip if already installed)"
pip install -r requirements.txt -q

Write-Host "==> [2/4] Run pipeline phases 1-4"
python run_all.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> [3/4] Pipeline summary"
python scripts/pipeline_summary.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> [4/4] Commit step (dry run)"
if (-not (Test-Path .git)) {
    Write-Host "Git repo not initialized - commit/push step skipped."
    Write-Host "Initialize git and push to GitHub before using Actions."
    exit 0
}

git add data/reviews.db
if (Test-Path data/exports/insights.csv) {
    git add data/exports/insights.csv
}
$diff = git diff --staged --name-only
if ($diff) {
    Write-Host "Files that would be committed:"
    $diff | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "No data changes to commit."
}

Write-Host "Local scheduler test complete."
