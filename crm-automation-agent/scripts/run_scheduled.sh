#!/usr/bin/env bash
# Scheduled CRM automation run, intended for cron.
#
# Usage:
#   scripts/run_scheduled.sh [source]
#
# Cron example (every weekday 08:00, auto-approving external actions, logging):
#   0 8 * * 1-5 cd /opt/crm-automation-agent && \
#     scripts/run_scheduled.sh hubspot >> /var/log/crm-automation.log 2>&1
#
# Uses --yes so external actions auto-approve (unattended). Every action is still
# audited to SQLite (CRM_DB_PATH), and a timestamped report is written to reports/.
# Email drafts are never sent — they are queued for human review in the report.
set -euo pipefail

SOURCE="${1:-demo}"

cd "$(dirname "$0")/.."

# Load .env if present (provides LITELLM_MODEL, provider + CRM credentials).
if [[ -f .env ]]; then
  set -a; . ./.env; set +a
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="reports/${STAMP}"

# Prefer the venv entry point if present, else the module.
if [[ -x .venv/bin/crm-automation ]]; then
  RUN=(.venv/bin/crm-automation)
else
  RUN=(python -m crm_automation)
fi

"${RUN[@]}" run --source "$SOURCE" --yes --out-dir "$OUT_DIR"
echo "Run report written to ${OUT_DIR}"
