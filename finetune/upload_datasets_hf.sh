#!/bin/bash
# Upload all datasets to HuggingFace Hub for use in Colab notebooks.
#
# Prerequisites:
#   pip install huggingface_hub[cli]
#   huggingface-cli login
#
# Usage:
#   ./upload_datasets_hf.sh                     # Uses default username
#   HF_USER=myuser ./upload_datasets_hf.sh      # Custom username

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATASETS_DIR="${SCRIPT_DIR}/datasets"
HF_USER="${HF_USER:-clemsail}"

DOMAINS="stm32 spice iot power dsp emc kicad embedded"

echo "Uploading datasets to HuggingFace Hub (user: ${HF_USER})"
echo ""

for domain in ${DOMAINS}; do
    file="${DATASETS_DIR}/${domain}_chat.jsonl"
    repo="${HF_USER}/mascarade-${domain}-dataset"

    if [[ ! -f "${file}" ]]; then
        echo "  SKIP ${domain}: file not found"
        continue
    fi

    lines=$(wc -l < "${file}")
    size=$(du -h "${file}" | cut -f1)
    echo "  ${domain}: ${lines} examples (${size}) -> ${repo}"

    huggingface-cli upload "${repo}" "${file}" "${domain}_chat.jsonl" --repo-type dataset 2>/dev/null || \
        echo "    WARN: upload failed for ${domain} (check huggingface-cli login)"
done

echo ""
echo "Done. Datasets available at:"
for domain in ${DOMAINS}; do
    echo "  https://huggingface.co/datasets/${HF_USER}/mascarade-${domain}-dataset"
done
