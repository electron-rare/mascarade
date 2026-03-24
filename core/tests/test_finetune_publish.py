"""Tests for finetune/publish.py — Ollama auto-registration."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.finetune.publish import (
    DEFAULT_TEMPLATE,
    build_modelfile,
    register_ollama_model,
)


class TestBuildModelfile:
    def test_default_template(self):
        mf = build_modelfile("/path/to/model.gguf")
        assert 'FROM "/path/to/model.gguf"' in mf
        assert "im_start" in mf
        assert "PARAMETER stop" in mf

    def test_custom_template(self):
        mf = build_modelfile("/m.gguf", template="custom {{ .Prompt }}")
        assert "custom {{ .Prompt }}" in mf
        assert DEFAULT_TEMPLATE not in mf

    def test_system_prompt(self):
        mf = build_modelfile("/m.gguf", system="You are a coder.")
        assert "You are a coder." in mf
        assert "SYSTEM" in mf

    def test_no_system_by_default(self):
        mf = build_modelfile("/m.gguf")
        assert "SYSTEM" not in mf


class TestRegisterOllamaModel:
    @pytest.mark.asyncio
    async def test_missing_gguf(self):
        result = await register_ollama_model("/nonexistent/model.gguf", "test-model")
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_ollama_binary(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"fake gguf")
            gguf_path = f.name
        try:
            result = await register_ollama_model(
                gguf_path, "test-model", ollama_binary="nonexistent-ollama-binary"
            )
            assert result["status"] == "error"
            assert "not found" in result["error"].lower()
        finally:
            Path(gguf_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_successful_registration(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"fake gguf")
            gguf_path = f.name

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"success\n", b""))

        try:
            with patch(
                "mascarade.finetune.publish.shutil.which",
                return_value="/usr/bin/ollama",
            ):
                with patch(
                    "mascarade.finetune.publish.asyncio.create_subprocess_exec",
                    return_value=mock_proc,
                ):
                    result = await register_ollama_model(gguf_path, "test-model")
                    assert result["status"] == "registered"
                    assert result["model_name"] == "test-model"
        finally:
            Path(gguf_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_failed_ollama_create(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"fake gguf")
            gguf_path = f.name

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"model error"))

        try:
            with patch(
                "mascarade.finetune.publish.shutil.which",
                return_value="/usr/bin/ollama",
            ):
                with patch(
                    "mascarade.finetune.publish.asyncio.create_subprocess_exec",
                    return_value=mock_proc,
                ):
                    result = await register_ollama_model(gguf_path, "test-model")
                    assert result["status"] == "error"
                    assert "model error" in result["error"]
        finally:
            Path(gguf_path).unlink(missing_ok=True)
