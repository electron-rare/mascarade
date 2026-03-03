#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/core/.venv"
ENV_FILE="$ROOT_DIR/.env"
[ -d "$VENV" ] || { echo "Missing venv: $VENV"; exit 1; }
source "$VENV/bin/activate"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
python3 - <<'PY'
import os,sys
import google.auth
from google.auth.transport.requests import Request
from google import genai
location=os.getenv('GOOGLE_CLOUD_LOCATION','europe-west1')
model=os.getenv('GOOGLE_MODEL','gemini-2.5-flash')
api_key=os.getenv('GOOGLE_API_KEY','')
adc_ok=False
try:
    creds,prj=google.auth.default(); creds.refresh(Request()); print(f"ADC_OK project={prj or ''}"); adc_ok=True
except Exception as exc:
    print(f"ADC_FAIL {exc}")
if not api_key and not adc_ok:
    print('GOOGLE_AUTH_FAIL no GOOGLE_API_KEY and no valid ADC'); sys.exit(2)
try:
    client=genai.Client(api_key=api_key or None)
    resp=client.models.generate_content(model=model,contents='Return exactly: pong',config={'temperature':0})
    print(f"GENAI_OK model={model} location={location} response={(getattr(resp,'text','') or '')[:80]!r}")
except Exception as exc:
    print(f"GENAI_FAIL {exc}"); sys.exit(3)
PY
