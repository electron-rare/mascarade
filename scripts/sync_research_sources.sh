#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=/ai/saisail/mascarade/scripts/lib.sh
source "${SCRIPT_DIR}/lib.sh"

DOMAINS_DIR="${REPO_DIR}/finetune/research_sources/domains"
DOC_PATH="${REPO_DIR}/docs/DATASET_DOMAIN_FORUMS.md"
SUMMARY_PATH="${REPO_DIR}/finetune/research_sources/summary.json"
PROBES_DIR="${REPO_DIR}/finetune/research_probes"
CHECK_ONLY=false
SKIP_WEB_PROBE=false
PROBE_DOMAIN_WORKERS=4

usage() {
    cat <<'EOF'
Usage: ./scripts/sync_research_sources.sh [options]

Validate domain web research JSON sources, regenerate the forum doc, and write a summary report.

Options:
  --check-only           Validate only, do not rewrite docs or summary.
  --summary-json PATH    Override summary output path.
  --doc PATH             Override generated markdown doc path.
  --skip-web-probe       Skip live HTTP probe of the registered web sources.
  --probe-domain-workers N
                         Parallel domain workers for the live probe (default: 4).
  -v, --verbose          Enable verbose logs.
  -h, --help             Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --summary-json)
            SUMMARY_PATH="$2"
            shift 2
            ;;
        --doc)
            DOC_PATH="$2"
            shift 2
            ;;
        --skip-web-probe)
            SKIP_WEB_PROBE=true
            shift
            ;;
        --probe-domain-workers)
            PROBE_DOMAIN_WORKERS="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

section "Research Sources Sync"
log "Domains dir: ${DOMAINS_DIR}"
[[ -d "${DOMAINS_DIR}" ]] || { err "Missing domains dir: ${DOMAINS_DIR}"; exit 1; }

PY_OUTPUT="$(python - "${DOMAINS_DIR}" "${DOC_PATH}" "${SUMMARY_PATH}" "${CHECK_ONLY}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

domains_dir = Path(sys.argv[1])
doc_path = Path(sys.argv[2])
summary_path = Path(sys.argv[3])
check_only = sys.argv[4].lower() == "true"

required_keys = [
    "topic",
    "authoritative_urls",
    "github_repos",
    "software_sources",
    "forum_urls",
    "datasheet_roots",
    "queries",
    "trusted_domains",
    "minimum_web_roots",
]
url_keys = [
    "authoritative_urls",
    "github_repos",
    "software_sources",
    "forum_urls",
    "datasheet_roots",
]

domain_files = sorted(domains_dir.glob("*.json"))
if not domain_files:
    raise SystemExit("No domain JSON files found")

domains = []
errors = []

for path in domain_files:
    payload = json.loads(path.read_text(encoding="utf-8"))
    domain = payload.get("domain") or path.stem
    missing = [key for key in required_keys if key not in payload]
    if missing:
        errors.append(f"{domain}: missing keys: {', '.join(missing)}")
        continue

    for key in url_keys:
        entries = payload.get(key, [])
        if not isinstance(entries, list):
            errors.append(f"{domain}: {key} must be a list")
            continue
        for idx, item in enumerate(entries, start=1):
            if not isinstance(item, dict) or not item.get("label") or not item.get("url"):
                errors.append(f"{domain}: {key}[{idx}] must have label/url")
                continue

    forum_count = len(payload.get("forum_urls", []))
    web_roots_count = sum(len(payload.get(key, [])) for key in url_keys) + len(payload.get("hf_sources", []))
    minimum_web_roots = int(payload.get("minimum_web_roots", 0))
    minimum_quality_score = int(payload.get("minimum_quality_score", 6))
    queries_count = len(payload.get("queries", []))
    trusted_count = len(payload.get("trusted_domains", []))
    quality_checks = {
        "authoritative_sources": len(payload.get("authoritative_urls", [])) >= 2,
        "github_or_software_sources": len(payload.get("github_repos", [])) + len(payload.get("software_sources", [])) >= 2,
        "forum_coverage": forum_count >= 4,
        "datasheet_or_vendor_roots": len(payload.get("datasheet_roots", [])) >= 1,
        "hf_or_dataset_roots": len(payload.get("hf_sources", [])) >= 1,
        "query_coverage": queries_count >= 3,
        "trusted_domains_coverage": trusted_count >= 3,
        "web_root_depth": web_roots_count >= minimum_web_roots,
    }
    quality_score = sum(1 for value in quality_checks.values() if value)

    if web_roots_count < minimum_web_roots:
        errors.append(f"{domain}: web_roots={web_roots_count} < minimum_web_roots={minimum_web_roots}")
    if queries_count == 0:
        errors.append(f"{domain}: queries is empty")
    if trusted_count == 0:
        errors.append(f"{domain}: trusted_domains is empty")
    if quality_score < minimum_quality_score:
        errors.append(f"{domain}: quality_score={quality_score} < minimum_quality_score={minimum_quality_score}")

    domains.append(
        {
            "domain": domain,
            "topic": payload["topic"],
            "file": str(path),
            "forum_count": forum_count,
            "web_roots_count": web_roots_count,
            "minimum_web_roots": minimum_web_roots,
            "quality_score": quality_score,
            "minimum_quality_score": minimum_quality_score,
            "queries_count": queries_count,
            "trusted_domains_count": trusted_count,
            "status": "ok",
            "forum_urls": payload["forum_urls"],
        }
    )

domains.sort(key=lambda item: item["domain"])
overall_status = "ok" if not errors else "failed"

summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "domains_dir": str(domains_dir),
    "doc_path": str(doc_path),
    "summary_path": str(summary_path),
    "status": overall_status,
    "domains": domains,
    "errors": errors,
}

if not check_only:
    doc_lines = [
        "# Dataset Domain Forums",
        "",
        "Canonical specialized forum/community roots used by the dataset research gate.",
        "",
        "Forum/community roots are one quality signal among others. They are not the hard gate.",
        "",
    ]
    for item in domains:
        doc_lines.append(f"## {item['domain']}")
        doc_lines.append("")
        for forum in item["forum_urls"]:
            doc_lines.append(f"- `{forum['url']}`")
        doc_lines.append("")
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("\n".join(doc_lines).rstrip() + "\n", encoding="utf-8")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(json.dumps(summary, indent=2, ensure_ascii=False))
sys.exit(1 if errors else 0)
PY
)"

status=$?
echo "${PY_OUTPUT}" > /tmp/mascarade_research_sync_summary.json

if [[ $status -ne 0 ]]; then
    err "Research source validation failed"
    sed -n '1,200p' /tmp/mascarade_research_sync_summary.json
    exit $status
fi

ok "Research sources validated"
if [[ "${CHECK_ONLY}" == true ]]; then
    info "Check-only mode: docs and summary not rewritten"
else
    ok "Forum doc updated: ${DOC_PATH}"
    ok "Summary updated: ${SUMMARY_PATH}"
fi

if [[ "${SKIP_WEB_PROBE}" != true ]]; then
    log "Running live HTTP probes for research sources"
    python "${REPO_DIR}/finetune/probe_research_sources.py" \
        --sources-dir "${DOMAINS_DIR}" \
        --output-dir "${PROBES_DIR}" \
        --max-domain-workers "${PROBE_DOMAIN_WORKERS}"
    ok "Research probes updated: ${PROBES_DIR}"
fi

python - <<'PY' /tmp/mascarade_research_sync_summary.json
import json
import sys
summary = json.loads(open(sys.argv[1], encoding="utf-8").read())
for item in summary["domains"]:
    print(f"{item['domain']}: forums={item['forum_count']} web_roots={item['web_roots_count']} queries={item['queries_count']} trusted={item['trusted_domains_count']} quality_score={item['quality_score']}")
PY
