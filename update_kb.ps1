# Incremental Misty Garden update: scrape new catalog URLs -> index into Qdrant.
# Run after adding new links to catalog/*.md (e.g. via inbox.txt + get_titles_v2.py).
# Both steps are idempotent: already processed URLs are skipped.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"

Write-Host "=== Step 1/2: scraping new articles ===" -ForegroundColor Cyan
& .venv\Scripts\python.exe scrape_articles.py
if ($LASTEXITCODE -ne 0) { Write-Warning "Scrape finished with warnings (yield < 70% or failures) — check raw/failed_urls.txt" }

Write-Host "=== Step 2/2: indexing into Qdrant ===" -ForegroundColor Cyan
& .venv\Scripts\python.exe index_articles.py

Write-Host "Done. Check collection: http://localhost:6333/dashboard" -ForegroundColor Green
