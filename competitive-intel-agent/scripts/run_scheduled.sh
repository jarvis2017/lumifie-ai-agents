#!/usr/bin/env bash
# Scheduled competitive-intel run, intended for cron.
#
# Usage:
#   scripts/run_scheduled.sh "Company Name" "market vertical"
#
# Cron example (every Monday 07:00, logging to a file):
#   0 7 * * 1 cd /opt/competitive-intel-agent && \
#     scripts/run_scheduled.sh "Acme" "project management SaaS" >> /var/log/ci-acme.log 2>&1
#
# Each run appends to the SQLite history (CI_DB_PATH) so the brief surfaces what
# changed since the previous run, and writes a timestamped copy under reports/.
set -euo pipefail

COMPANY="${1:?usage: run_scheduled.sh <company> <vertical>}"
VERTICAL="${2:?usage: run_scheduled.sh <company> <vertical>}"

cd "$(dirname "$0")/.."

# Load .env if present (provides LITELLM_MODEL and provider API keys).
if [[ -f .env ]]; then
  set -a; . ./.env; set +a
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="reports/${STAMP}"

# Prefer the venv entry point if present, else the module.
if [[ -x .venv/bin/competitive-intel ]]; then
  RUN=(.venv/bin/competitive-intel)
else
  RUN=(python -m competitive_intel)
fi

"${RUN[@]}" --company "$COMPANY" --vertical "$VERTICAL" --out-dir "$OUT_DIR"
echo "Brief written to ${OUT_DIR}"
