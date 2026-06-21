#!/usr/bin/env bash
# Scheduled regulatory-monitor run, intended for cron (weekly digests).
#
# Usage:
#   scripts/run_scheduled.sh [path/to/profile.json]
#
# Cron example (every Monday 07:00, logging to a file):
#   0 7 * * 1 cd /opt/regulatory-monitor-agent && \
#     scripts/run_scheduled.sh config/profile.example.json >> /var/log/reg-monitor.log 2>&1
#
# Each run appends to the SQLite history (RM_DB_PATH) so the digest surfaces what's
# new since the previous run, and writes a timestamped copy under reports/.
set -euo pipefail

PROFILE="${1:-config/profile.example.json}"

cd "$(dirname "$0")/.."

# Load .env if present (provides LITELLM_MODEL and provider API keys).
if [[ -f .env ]]; then
  set -a; . ./.env; set +a
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="reports/${STAMP}"

# Prefer the venv entry point if present, else the module.
if [[ -x .venv/bin/reg-monitor ]]; then
  RUN=(.venv/bin/reg-monitor)
else
  RUN=(python -m reg_monitor)
fi

"${RUN[@]}" --profile "$PROFILE" --out-dir "$OUT_DIR"
echo "Digest written to ${OUT_DIR}"
