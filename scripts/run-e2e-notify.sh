#!/usr/bin/env bash
set -uo pipefail
cd /home/clems/mascarade/web || exit 1
docker network connect mascarade-main_mascarade-network mascarade-api 2>/dev/null
RESULT=$(BASE_URL=http://localhost:3100 npx playwright test --reporter=line 2>&1)
PASSED=$(echo "$RESULT" | grep -oP '\d+ passed' | grep -oP '\d+' || echo 0)
FAILED=$(echo "$RESULT" | grep -oP '\d+ failed' | grep -oP '\d+' || echo 0)
if [ "${FAILED:-0}" != "0" ] && [ "${FAILED:-0}" != "" ]; then
  curl -s -d "E2E FAILED: $FAILED tests at $(date '+%H:%M %d/%m')" -H 'Title: Ops ER E2E Failed' -H 'Priority: high' -H 'Tags: rotating_light' https://ntfy.saillant.cc/ops-alerts
else
  curl -s -d "E2E OK: $PASSED passed at $(date '+%H:%M %d/%m')" -H 'Title: Ops ER E2E' -H 'Priority: min' -H 'Tags: white_check_mark' https://ntfy.saillant.cc/ops-alerts
fi
