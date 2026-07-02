# Validate GitHub Actions scheduler setup (local checks only).

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== GitHub Actions configuration check ===" -ForegroundColor Cyan

$ok = $true

# 1. Workflow file exists and YAML parses
$workflow = ".github/workflows/weekly-pipeline.yml"
if (-not (Test-Path $workflow)) {
    Write-Host "[FAIL] Missing $workflow" -ForegroundColor Red
    $ok = $false
} else {
    python -c "import yaml; yaml.safe_load(open(r'$workflow')); print('[OK] Workflow YAML syntax')"
    if ($LASTEXITCODE -ne 0) { $ok = $false }
}

# 2. Required scripts
foreach ($file in @("scripts/pipeline_summary.py", "scripts/test-scheduler-local.ps1", "run_all.py")) {
    if (Test-Path $file) {
        Write-Host "[OK] Found $file"
    } else {
        Write-Host "[FAIL] Missing $file" -ForegroundColor Red
        $ok = $false
    }
}

# 3. Data files for commit step
if (Test-Path "data/reviews.db") {
    $sizeMb = [math]::Round((Get-Item "data/reviews.db").Length / 1MB, 2)
    Write-Host "[OK] data/reviews.db exists ($sizeMb MB)"
} else {
    Write-Host "[WARN] data/reviews.db missing - run pipeline first" -ForegroundColor Yellow
}

if (Test-Path "data/exports/insights.csv") {
    Write-Host "[OK] data/exports/insights.csv exists"
} else {
    Write-Host "[WARN] data/exports/insights.csv missing - run phase 4 first" -ForegroundColor Yellow
}

# 4. Git repository
if (Test-Path .git) {
    Write-Host "[OK] Git repository initialized"
    $remote = git remote get-url origin 2>$null
    if ($remote) {
        Write-Host "[OK] Git remote: $remote"
    } else {
        Write-Host "[WARN] No git remote 'origin' - push to GitHub to enable Actions" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] Not a git repository - run: git init" -ForegroundColor Red
    $ok = $false
}

# 5. GitHub CLI auth
$ghStatus = gh auth status 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] GitHub CLI authenticated"
} else {
    Write-Host "[WARN] GitHub CLI not authenticated - run: gh auth login" -ForegroundColor Yellow
}

# 6. Remote workflow visibility (if origin exists and gh works)
if ((Test-Path .git) -and (git remote get-url origin 2>$null)) {
    $repo = gh repo view --json nameWithOwner -q .nameWithOwner 2>$null
    if ($repo) {
        Write-Host "[OK] GitHub repo detected: $repo"
        $workflows = gh workflow list 2>$null
        if ($LASTEXITCODE -eq 0 -and $workflows) {
            Write-Host "[OK] Workflows on GitHub:"
            $workflows | ForEach-Object { Write-Host "     $_" }
        } else {
            Write-Host "[WARN] Workflow not on GitHub yet - push .github/workflows/weekly-pipeline.yml" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Required GitHub Actions secrets (set in repo Settings):" -ForegroundColor Cyan
Write-Host "  GROQ_API_KEY            (required)"

Write-Host ""
if ($ok) {
    Write-Host "Local configuration looks good. Push to GitHub and run the workflow manually once." -ForegroundColor Green
} else {
    Write-Host "Fix the items marked FAIL before relying on GitHub Actions." -ForegroundColor Red
}
