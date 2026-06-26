#!/bin/bash
# cron_run.sh
# Runs the short ops monitor daily at 7:30 AM and commits the updated dashboard to GitHub Pages.
#
# Setup (run once):
#   chmod +x cron_run.sh
#   crontab -e
#   Add: 30 7 * * 1-5 /path/to/short_ops_monitor/cron_run.sh >> /path/to/short_ops_monitor/logs/cron.log 2>&1
#
# Runs Monday–Friday only (days 1-5).

set -e

# ── Config ──────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON_PATH:-python3}"   # override with: PYTHON_PATH=/path/to/python3 ./cron_run.sh
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "========================================"  | tee -a "$LOG_FILE"
echo "Short Ops Monitor | $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================"  | tee -a "$LOG_FILE"

# ── Run pipeline ─────────────────────────────────────────────────────────────
cd "$REPO_DIR"
$PYTHON run.py 2>&1 | tee -a "$LOG_FILE"

# ── Commit updated dashboard to GitHub Pages ─────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "Committing dashboard..." | tee -a "$LOG_FILE"

git add docs/index.html
git diff --cached --quiet && echo "No changes to commit." | tee -a "$LOG_FILE" || {
    git commit -m "chore: daily dashboard refresh $(date +%Y-%m-%d)"
    git push origin main
    echo "Pushed to GitHub Pages." | tee -a "$LOG_FILE"
}

echo "Done. $(date '+%H:%M:%S')" | tee -a "$LOG_FILE"
