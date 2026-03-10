#!/bin/bash
# Upload canonical datasets to Hugging Face Hub after local packaging.
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
PREPARE_SCRIPT="${SCRIPT_DIR}/prepare_hf_dataset.py"
HF_DATASETS_DIR="${SCRIPT_DIR}/hf_datasets"
HF_USER="${HF_USER:-clemsail}"

DOMAINS="stm32 spice iot power dsp emc kicad embedded platformio freecad components"

echo "Uploading datasets to HuggingFace Hub (user: ${HF_USER})"
echo ""

for domain in ${DOMAINS}; do
    python3 "${PREPARE_SCRIPT}" "${domain}" --username "${HF_USER}" >/dev/null

    package_dir="${HF_DATASETS_DIR}/${domain}"
    file="${package_dir}/${domain}_chat.jsonl"
    readme="${package_dir}/README.md"
    metadata="${package_dir}/metadata.json"
    repo="${HF_USER}/mascarade-${domain}-dataset"

    if [[ ! -f "${file}" ]]; then
        echo "  SKIP ${domain}: file not found"
        continue
    fi

    lines=$(wc -l < "${file}")
    size=$(du -h "${file}" | cut -f1)
    echo "  ${domain}: ${lines} examples (${size}) -> ${repo}"

    huggingface-cli upload "${repo}" "${readme}" "README.md" --repo-type dataset 2>/dev/null || \
        echo "    WARN: README upload failed for ${domain} (check huggingface-cli login)"
    huggingface-cli upload "${repo}" "${file}" "${domain}_chat.jsonl" --repo-type dataset 2>/dev/null || \
        echo "    WARN: dataset upload failed for ${domain} (check huggingface-cli login)"
    huggingface-cli upload "${repo}" "${metadata}" "metadata.json" --repo-type dataset 2>/dev/null || \
        echo "    WARN: metadata upload failed for ${domain} (check huggingface-cli login)"
done

echo ""
echo "Done. Datasets available at:"
for domain in ${DOMAINS}; do
    echo "  https://huggingface.co/datasets/${HF_USER}/mascarade-${domain}-dataset"
done
