#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TARGET_DIR="${TARGET_DIR:-/home/clems/tools/python-tools}"
VENV_DIR="${VENV_DIR:-${TARGET_DIR}/.venv}"
BASE_REQ_FILE="${REPO_DIR}/deploy/migration/python-tools.requirements.txt"
EXTRA_REQ_FILE="${REPO_DIR}/deploy/migration/python-tools.extras.requirements.txt"
REINSTALL=false

usage() {
  cat <<'EOF'
Usage: bash scripts/bootstrap_python_tools_env.sh [options]

Create or refresh the shared python-tools virtualenv used for migration-side tools.

Options:
  --python BIN       Python interpreter to use (default: PYTHON_BIN or python3)
  --target-dir PATH  Target python-tools directory (default: /home/clems/tools/python-tools)
  --venv-dir PATH    Virtualenv path (default: <target-dir>/.venv)
  --reinstall        Remove and recreate the venv before install
  -h, --help         Show this help

Installed layers:
  - deploy/migration/python-tools.requirements.txt
  - deploy/migration/python-tools.extras.requirements.txt

Post-install validation:
  - autogen_agentchat, dspy, instructor, llama_index, litellm
  - docling, whisper
  - local ffmpeg shim via imageio-ffmpeg into <venv>/bin/ffmpeg
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --python" >&2; usage >&2; exit 2; }
      PYTHON_BIN="$1"
      ;;
    --target-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --target-dir" >&2; usage >&2; exit 2; }
      TARGET_DIR="$1"
      [[ -n "${VENV_DIR:-}" ]] && VENV_DIR="${TARGET_DIR}/.venv"
      ;;
    --venv-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --venv-dir" >&2; usage >&2; exit 2; }
      VENV_DIR="$1"
      ;;
    --reinstall)
      REINSTALL=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

for req_file in "$BASE_REQ_FILE" "$EXTRA_REQ_FILE"; do
  [[ -f "$req_file" ]] || { echo "Requirements file not found: $req_file" >&2; exit 1; }
done

mkdir -p "${TARGET_DIR}"

if [[ "${REINSTALL}" == true && -d "${VENV_DIR}" ]]; then
  echo "[bootstrap-python-tools] removing ${VENV_DIR}"
  rm -rf "${VENV_DIR}"
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[bootstrap-python-tools] creating ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "[bootstrap-python-tools] reusing ${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/python" -m pip install -r "${BASE_REQ_FILE}" -r "${EXTRA_REQ_FILE}"

FFMPEG_BIN="$("${VENV_DIR}/bin/python" - <<'PY'
import imageio_ffmpeg
print(imageio_ffmpeg.get_ffmpeg_exe())
PY
)"

if [[ ! -x "${VENV_DIR}/bin/ffmpeg" || "$(readlink -f "${VENV_DIR}/bin/ffmpeg" 2>/dev/null || true)" != "$(readlink -f "${FFMPEG_BIN}")" ]]; then
  ln -sf "${FFMPEG_BIN}" "${VENV_DIR}/bin/ffmpeg"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib
modules = [
    "autogen_agentchat",
    "dspy",
    "instructor",
    "llama_index",
    "litellm",
    "docling",
    "whisper",
    "imageio_ffmpeg",
]
missing = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")
if missing:
    raise SystemExit("Import validation failed:\n" + "\n".join(missing))
PY

"${VENV_DIR}/bin/ffmpeg" -version >/dev/null

echo "[bootstrap-python-tools] python:  ${VENV_DIR}/bin/python"
echo "[bootstrap-python-tools] ffmpeg:  ${VENV_DIR}/bin/ffmpeg"
echo "[bootstrap-python-tools] target:  ${TARGET_DIR}"
