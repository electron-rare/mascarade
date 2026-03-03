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
import os,sys,boto3
from botocore.exceptions import BotoCoreError, ClientError
region=os.getenv('AWS_REGION','eu-west-1')
model_id=os.getenv('AWS_BEDROCK_MODEL_ID','')
try:
    sts=boto3.client('sts',region_name=region)
    ident=sts.get_caller_identity()
    print(f"STS_OK account={ident.get('Account')} arn={ident.get('Arn')}")
except Exception as exc:
    print(f"STS_FAIL {exc}")
    sys.exit(2)
try:
    bedrock=boto3.client('bedrock',region_name=region)
    resp=bedrock.list_foundation_models(byOutputModality='TEXT')
    print(f"BEDROCK_LIST_OK region={region} models={len(resp.get('modelSummaries',[]))}")
except (BotoCoreError, ClientError) as exc:
    print(f"BEDROCK_LIST_FAIL {exc}")
    sys.exit(3)
print(f"BEDROCK_MODEL_CONFIGURED {model_id or '<empty>'}")
PY
