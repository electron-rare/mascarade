#!/bin/bash
# Deploy a fine-tuned GGUF model to Ollama
#
# Usage:
#   ./deploy_model.sh <domain> <hf_repo>
#   ./deploy_model.sh stm32 clems/mascarade-stm32-q4km
#   ./deploy_model.sh spice clems/mascarade-spice-q4km
#
# This script:
#   1. Downloads the GGUF from HuggingFace Hub
#   2. Creates the Ollama model with domain-specific Modelfile
#   3. Tests the model with a simple prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${SCRIPT_DIR}/models"
MODELFILES_DIR="${SCRIPT_DIR}/modelfiles"

VALID_DOMAINS="stm32 spice iot power dsp emc kicad embedded"

usage() {
    echo "Usage: $0 <domain> <hf_repo>"
    echo ""
    echo "Domains: ${VALID_DOMAINS}"
    echo ""
    echo "Examples:"
    echo "  $0 stm32 clems/mascarade-stm32-q4km"
    echo "  $0 spice clems/mascarade-spice-q4km"
    echo "  $0 iot clems/mascarade-iot-q4km"
    echo "  $0 power clems/mascarade-power-q4km"
    echo "  $0 dsp clems/mascarade-dsp-q4km"
    echo "  $0 emc clems/mascarade-emc-q4km"
    echo "  $0 kicad clems/mascarade-kicad-q4km"
    echo "  $0 embedded clems/mascarade-embedded-q4km"
    exit 1
}

# Check arguments
[[ $# -ne 2 ]] && usage

DOMAIN="$1"
HF_REPO="$2"
MODEL_NAME="mascarade-${DOMAIN}"

# Validate domain
if ! echo "${VALID_DOMAINS}" | grep -qw "${DOMAIN}"; then
    echo "Error: Invalid domain '${DOMAIN}'"
    echo "Valid domains: ${VALID_DOMAINS}"
    exit 1
fi

# Check Modelfile exists
MODELFILE="${MODELFILES_DIR}/Modelfile.${DOMAIN}"
if [[ ! -f "${MODELFILE}" ]]; then
    echo "Error: Modelfile not found: ${MODELFILE}"
    exit 1
fi

# Check huggingface-cli is available
if ! command -v huggingface-cli &>/dev/null; then
    echo "Error: huggingface-cli not found"
    echo "Install: pip install huggingface_hub[cli]"
    exit 1
fi

echo "=========================================="
echo "Deploying ${DOMAIN} model from ${HF_REPO}"
echo "=========================================="

# Step 1: Download GGUF from HuggingFace
DOWNLOAD_DIR="${MODELS_DIR}/${DOMAIN}"
mkdir -p "${DOWNLOAD_DIR}"

echo ""
echo "[1/4] Downloading GGUF from HuggingFace..."
huggingface-cli download "${HF_REPO}" --local-dir "${DOWNLOAD_DIR}" --include "*.gguf"

# Find the GGUF file
GGUF_FILE=$(find "${DOWNLOAD_DIR}" -name "*.gguf" -type f | head -1)
if [[ -z "${GGUF_FILE}" ]]; then
    echo "Error: No GGUF file found in ${DOWNLOAD_DIR}"
    exit 1
fi
echo "  Found: ${GGUF_FILE}"

# Step 2: Create temporary Modelfile with correct path
echo ""
echo "[2/4] Creating Ollama model..."
TEMP_MODELFILE=$(mktemp)
sed "s|FROM ./model.gguf|FROM ${GGUF_FILE}|" "${MODELFILE}" > "${TEMP_MODELFILE}"

# Step 3: Create Ollama model
ollama create "${MODEL_NAME}" -f "${TEMP_MODELFILE}"
rm -f "${TEMP_MODELFILE}"
echo "  Model created: ${MODEL_NAME}"

# Step 4: Test
echo ""
echo "[3/4] Testing model..."
TEST_PROMPTS_stm32="Write a simple GPIO toggle on STM32F4"
TEST_PROMPTS_spice="Write a SPICE netlist for a voltage divider"
TEST_PROMPTS_iot="Write MQTT publish code for ESP32"
TEST_PROMPTS_power="Calculate inductor value for a buck converter"
TEST_PROMPTS_dsp="Implement a moving average filter in C"
TEST_PROMPTS_emc="What capacitor value for a Pi EMI filter?"
TEST_PROMPTS_kicad="How to set up DRC rules in KiCad for JLCPCB?"
TEST_PROMPTS_embedded="Write bare-metal ARM Cortex-M4 SysTick timer init"

PROMPT_VAR="TEST_PROMPTS_${DOMAIN}"
TEST_PROMPT="${!PROMPT_VAR}"

echo "  Prompt: ${TEST_PROMPT}"
echo "  Response:"
echo "  ---"
ollama run "${MODEL_NAME}" "${TEST_PROMPT}" 2>/dev/null | head -20
echo "  ---"

# Done
echo ""
echo "[4/4] Deployment complete!"
echo "=========================================="
echo "Model: ${MODEL_NAME}"
echo "GGUF:  ${GGUF_FILE}"
echo ""
echo "Usage:"
echo "  ollama run ${MODEL_NAME} 'your prompt here'"
echo ""
echo "Available in Mascarade via OllamaProvider:"
echo "  provider='ollama', model='${MODEL_NAME}'"
echo "=========================================="
