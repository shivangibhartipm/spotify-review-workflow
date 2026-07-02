# Validate Streamlit Community Cloud deployment readiness.

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== Streamlit deploy readiness ===" -ForegroundColor Cyan

$ok = $true

foreach ($file in @(
    "streamlit_app.py",
    "dashboard/app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    "data/reviews.db"
)) {
    if (Test-Path $file) {
        Write-Host "[OK] $file"
    } else {
        Write-Host "[FAIL] Missing $file" -ForegroundColor Red
        $ok = $false
    }
}

if (Test-Path "data/reviews.db") {
    $sizeMb = [math]::Round((Get-Item "data/reviews.db").Length / 1MB, 2)
    if ($sizeMb -gt 100) {
        Write-Host "[WARN] reviews.db is ${sizeMb}MB - GitHub limit is 100MB per file" -ForegroundColor Yellow
    }
}

python -c "from dashboard.app import main; print('[OK] dashboard.app imports')"
if ($LASTEXITCODE -ne 0) { $ok = $false }

if (-not (Test-Path .git)) {
    Write-Host "[WARN] Git not initialized - push to GitHub before deploying" -ForegroundColor Yellow
} else {
    $tracked = git ls-files data/reviews.db 2>$null
    if ($tracked) {
        Write-Host "[OK] data/reviews.db is tracked by git"
    } else {
        Write-Host "[WARN] data/reviews.db not tracked - run: git add data/reviews.db" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Deploy: https://share.streamlit.io -> Main file: streamlit_app.py"
Write-Host "Guide:  docs/deploy.md"
Write-Host ""

if ($ok) {
    Write-Host "Ready for Streamlit Community Cloud deployment." -ForegroundColor Green
} else {
    Write-Host "Fix FAIL items before deploying." -ForegroundColor Red
}
