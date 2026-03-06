"""HTTP tests for the standalone Apple LLM service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import httpx
import pytest


SERVICE_PATH = Path(__file__).resolve().parents[2] / "deploy" / "apple_llm_api" / "app.py"


def _load_service_module():
    spec = spec_from_file_location("test_apple_llm_service_app", SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@asynccontextmanager
async def _client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
def service_module():
    return _load_service_module()


@pytest.mark.asyncio
async def test_health_reports_missing_configuration(monkeypatch, service_module):
    monkeypatch.delenv("APPLE_LLM_MODEL_PATH", raising=False)
    monkeypatch.delenv("APPLE_LLM_TOKENIZER_PATH", raising=False)

    async with _client(service_module.app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["runtime_ready"] is False
    assert response.json()["configured"] is False


@pytest.mark.asyncio
async def test_models_and_generate_use_fake_runtime(monkeypatch, service_module):
    monkeypatch.setenv("APPLE_LLM_MODEL_PATH", "/tmp/model.mlpackage")
    monkeypatch.setenv("APPLE_LLM_TOKENIZER_PATH", "/tmp/tokenizer")
    monkeypatch.setenv("APPLE_LLM_MODEL_ID", "phi-3-mini-coreml")

    class _FakeRuntime:
        backend_name = "coreml"

        def dependency_versions(self):
            return {"numpy": "test", "transformers": "test", "coremltools": "test"}

        def available_models(self):
            return ["phi-3-mini-coreml"]

        def describe(self):
            return {
                "backend": "coreml",
                "model_id": "phi-3-mini-coreml",
                "model_path": "/tmp/model.mlpackage",
                "tokenizer_path": "/tmp/tokenizer",
                "compute_units": "cpu_and_ne",
                "model_loaded": False,
            }

        def generate(self, req):
            return {
                "content": "apple runtime ok",
                "model": "phi-3-mini-coreml",
                "backend": "coreml",
                "finish_reason": "stop",
                "usage": {"input_tokens": 12, "output_tokens": 3},
            }

    monkeypatch.setattr(service_module, "_build_runtime", lambda config: _FakeRuntime())

    async with _client(service_module.app) as client:
        models_response = await client.get("/models")
        generate_response = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "hello"}],
                "model": "phi-3-mini-coreml",
                "temperature": 0,
                "max_tokens": 32,
            },
        )

    assert models_response.status_code == 200
    assert models_response.json() == {
        "models": ["phi-3-mini-coreml"],
        "backend": "coreml",
    }
    assert generate_response.status_code == 200
    assert generate_response.json()["content"] == "apple runtime ok"


def test_prompt_fallback(service_module):
    prompt = service_module._fallback_prompt(
        [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
        system="stay brief",
    )

    assert "System: stay brief" in prompt
    assert prompt.endswith("Assistant:")


def test_prepare_inputs_supports_empty_past_cache(service_module):
    runtime = object.__new__(service_module._IterativeDecoderRuntime)
    np = pytest.importorskip("numpy")

    runtime._np = np
    runtime.backend_name = "onnx-coreml"
    runtime._input_specs = [
        ("input_ids", "tensor(int64)", ["batch_size", "sequence_length"]),
        ("attention_mask", "tensor(int64)", ["batch_size", "total_sequence_length"]),
        ("position_ids", "tensor(int64)", ["batch_size", "sequence_length"]),
        ("past_key_values.0.key", "tensor(float16)", ["batch_size", 3, "past_sequence_length", 64]),
    ]
    runtime._tokenizer = object()

    inputs = runtime._prepare_inputs(np.array([[1, 2, 3]], dtype=np.int64))

    assert tuple(inputs["attention_mask"].shape) == (1, 3)
    assert tuple(inputs["position_ids"].shape) == (1, 3)
    assert tuple(inputs["past_key_values.0.key"].shape) == (1, 3, 0, 64)


def test_prepare_inputs_supports_embed_tokens_and_qwen35_cache(service_module):
    runtime = object.__new__(service_module._IterativeDecoderRuntime)
    np = pytest.importorskip("numpy")

    runtime._np = np
    runtime.backend_name = "onnx-coreml"
    runtime._input_specs = [
        ("inputs_embeds", "tensor(float)", ["batch_size", "sequence_length", 2560]),
        ("attention_mask", "tensor(int64)", ["batch_size", "total_sequence_length"]),
        ("position_ids", "tensor(int64)", [3, "batch_size", "sequence_length"]),
        ("past_conv.0", "tensor(float16)", ["batch_size", 8192, 4]),
        ("past_recurrent.0", "tensor(float16)", ["batch_size", 32, 128, 128]),
        ("past_key_values.3.key", "tensor(float16)", ["batch_size", 4, "past_sequence_length", 256]),
    ]
    runtime._tokenizer = object()
    runtime._embed_input_ids = lambda token_ids: np.ones((1, token_ids.shape[1], 2560), dtype=np.float32)

    inputs = runtime._prepare_inputs(np.array([[7, 8]], dtype=np.int64))

    assert tuple(inputs["inputs_embeds"].shape) == (1, 2, 2560)
    assert tuple(inputs["attention_mask"].shape) == (1, 2)
    assert tuple(inputs["position_ids"].shape) == (3, 1, 2)
    assert tuple(inputs["past_conv.0"].shape) == (1, 8192, 4)
    assert tuple(inputs["past_recurrent.0"].shape) == (1, 32, 128, 128)
    assert tuple(inputs["past_key_values.3.key"].shape) == (1, 4, 0, 256)


def test_extract_cache_state_supports_qwen35_outputs(service_module):
    runtime = object.__new__(service_module._IterativeDecoderRuntime)
    np = pytest.importorskip("numpy")

    outputs = {
        "present.3.key": np.zeros((1, 4, 5, 256), dtype=np.float16),
        "present.3.value": np.zeros((1, 4, 5, 256), dtype=np.float16),
        "present_conv.0": np.zeros((1, 8192, 4), dtype=np.float16),
        "present_recurrent.0": np.zeros((1, 32, 128, 128), dtype=np.float16),
    }

    remapped = runtime._extract_cache_state(outputs)

    assert set(remapped) == {
        "past_key_values.3.key",
        "past_key_values.3.value",
        "past_conv.0",
        "past_recurrent.0",
    }


def test_resolve_embed_model_path_for_qwen35_layout(tmp_path, service_module):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    decoder_path = model_dir / "decoder_model_merged_q4f16.onnx"
    embed_path = model_dir / "embed_tokens_q4f16.onnx"
    decoder_path.write_text("decoder")
    embed_path.write_text("embed")

    runtime = object.__new__(service_module.OnnxCoreMLRuntime)
    runtime.config = service_module.RuntimeConfig(
        backend="onnx-coreml",
        model_id="qwen3.5-4b-q4f16",
        model_path=str(decoder_path),
        tokenizer_path=str(model_dir),
        compute_units="cpu_and_ne",
        max_input_tokens=2048,
        max_new_tokens=256,
        trust_remote_code=False,
    )

    assert runtime._resolve_embed_model_path() == str(embed_path)
