from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prepare_runtime_step_prints_switch_commands(tmp_path):
    home = tmp_path / "home"
    model_root = home / "Models" / "mascarade" / "apple-llm" / "Qwen3.5-4B-ONNX-q4f16" / "onnx"
    model_root.mkdir(parents=True)
    (model_root / "decoder_model_merged_q4f16.onnx").write_text("x", encoding="utf-8")
    (model_root / "embed_tokens_q4f16.onnx").write_text("x", encoding="utf-8")

    tokenizer_root = home / "Models" / "mascarade" / "apple-llm" / "Qwen3.5-4B-ONNX-q4f16"
    (tokenizer_root / "tokenizer.json").write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            "scripts/prepare_runtime_step.sh",
            "--apple-model",
            "qwen3.5-4b-onnx-q4f16",
            "--resume-state",
            "/tmp/state.json",
            "--ane-script",
            "/tmp/ane/scripts/run_next_lots.py",
        ],
        cwd=REPO_ROOT,
        env={"HOME": str(home), "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin"))},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "export APPLE_LLM_MODEL_ID=qwen3.5-4b-onnx-q4f16" in result.stdout
    assert "pkill -f \"uvicorn app:app\" || true" in result.stdout
    assert "python3 /tmp/ane/scripts/run_next_lots.py --resume /tmp/state.json" in result.stdout


def test_ensure_apple_models_check_only_is_idempotent(tmp_path):
    home = tmp_path / "home"
    qwen05 = home / "Models" / "mascarade" / "apple-llm" / "Qwen2.5-0.5B-Instruct-model" / "onnx"
    qwen05.mkdir(parents=True)
    (qwen05 / "model.onnx").write_text("x", encoding="utf-8")
    qwen05_root = home / "Models" / "mascarade" / "apple-llm" / "Qwen2.5-0.5B-Instruct-model"
    (qwen05_root / "tokenizer.json").write_text("{}", encoding="utf-8")

    qwen35 = home / "Models" / "mascarade" / "apple-llm" / "Qwen3.5-4B-ONNX-q4f16" / "onnx"
    qwen35.mkdir(parents=True)
    (qwen35 / "decoder_model_merged_q4f16.onnx").write_text("x", encoding="utf-8")
    (qwen35 / "embed_tokens_q4f16.onnx").write_text("x", encoding="utf-8")
    qwen35_root = home / "Models" / "mascarade" / "apple-llm" / "Qwen3.5-4B-ONNX-q4f16"
    (qwen35_root / "tokenizer.json").write_text("{}", encoding="utf-8")

    mistral = home / "Models" / "mascarade" / "apple-llm" / "StatefulMistral7BInstructInt4"
    mistral.mkdir(parents=True)
    (mistral / "StatefulMistral7BInstructInt4.mlpackage").write_text("x", encoding="utf-8")
    (mistral / "tokenizer").mkdir()

    result = subprocess.run(
        ["bash", "scripts/ensure_apple_models.sh", "--check-only"],
        cwd=REPO_ROOT,
        env={"HOME": str(home), "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin"))},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "qwen2.5-0.5b-instruct-onnx: present" in result.stdout
    assert "qwen3.5-4b-onnx-q4f16: present" in result.stdout
    assert "stateful-mistral7b-instruct-int4-coreml: present" in result.stdout
