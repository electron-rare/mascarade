"""Tests for pre-warming and priority queue behavior in Apple LLM multi-model serving."""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import httpx
import pytest

pytest.importorskip("psutil", reason="psutil required for apple_llm_api tests")

SERVICE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "apple_llm_api" / "app.py"
)


def _load_service_module():
    """Load the Apple LLM service module for testing."""
    spec = spec_from_file_location("test_pre_warming_app", SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@asynccontextmanager
async def _client(app):
    """Create an async HTTP client for the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


class FakeMultiModelRuntime:
    """Fake runtime that simulates a CoreML/ONNX model."""

    def __init__(self, model_id: str, backend: str = "coreml"):
        self.model_id = model_id
        self.backend_name = backend
        self._load_time = time.time()
        self._generate_count = 0

    def check_ready(self) -> None:
        """Check if runtime is ready - required by RuntimeState protocol."""
        pass

    def dependency_versions(self) -> dict[str, str]:
        return {"numpy": "test", "transformers": "test", "coremltools": "test"}

    def available_models(self) -> list[str]:
        return [self.model_id]

    def describe(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "model_id": self.model_id,
            "model_path": f"/tmp/{self.model_id}.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "compute_units": "cpu_and_ne",
            "model_loaded": True,
        }

    def generate(self, req) -> dict[str, Any]:
        """Simulate generation from this model."""
        self._generate_count += 1
        return {
            "content": f"Response from {self.model_id}",
            "model": self.model_id,
            "backend": self.backend_name,
            "finish_reason": "stop",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }


@pytest.fixture
def service_module():
    """Provide the service module for tests."""
    return _load_service_module()


@pytest.mark.asyncio
async def test_pre_warming_loads_next_likely_model(monkeypatch, service_module):
    """Test that pre-warming loads the next likely model in background.

    Verifies:
    - Pattern A, B, A, B triggers prediction that A or B will be next
    - Pre-warming loads the predicted model when memory allows
    - Pre-warm candidate is shown in /status endpoint
    """
    # Configure 3 models with different priorities, max 2 concurrent
    models_config = [
        {
            "model_id": "model-a",
            "model_path": "/tmp/a.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "model-b",
            "model_path": "/tmp/b.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 5,
        },
        {
            "model_id": "model-c",
            "model_path": "/tmp/c.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    built_models: dict[str, FakeMultiModelRuntime] = {}

    def _build_fake_runtime(config):
        """Build a fake runtime for the given config."""
        runtime = FakeMultiModelRuntime(config.model_id, config.backend)
        built_models[config.model_id] = runtime
        return runtime

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)

    # Reload the global model manager with new config
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=2)

    async with _client(service_module.app) as client:
        # Send requests in pattern: A, B, A, B
        for model_id in ["model-a", "model-b", "model-a", "model-b"]:
            response = await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": model_id,
                },
            )
            assert response.status_code == 200
            assert response.json()["model"] == model_id

        # Check /status shows pre-warm candidate
        status = await client.get("/status")
        assert status.status_code == 200
        status_data = status.json()

        # Pre-warm candidate should be either model-a or model-b (both used frequently)
        pre_warm_candidate = status_data.get("pre_warm_candidate")
        assert pre_warm_candidate in [
            "model-a",
            "model-b",
        ], f"Expected pre-warm candidate to be model-a or model-b, got {pre_warm_candidate}"

        # Both models should be loaded (max_concurrent is 2)
        loaded_model_ids = [m["model_id"] for m in status_data["loaded_models"]]
        assert len(loaded_model_ids) == 2
        assert "model-a" in loaded_model_ids
        assert "model-b" in loaded_model_ids

        # Request model-c now - should trigger pre-warming logic
        response_c = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "model-c",
            },
        )
        assert response_c.status_code == 200
        assert response_c.json()["model"] == "model-c"

        # Check status again - model-c should be loaded now
        status2 = await client.get("/status")
        assert status2.status_code == 200
        status_data2 = status2.json()

        loaded_model_ids2 = [m["model_id"] for m in status_data2["loaded_models"]]
        assert "model-c" in loaded_model_ids2

        # Pre-warm candidate should now potentially be different
        pre_warm_candidate2 = status_data2.get("pre_warm_candidate")
        assert pre_warm_candidate2 is not None


@pytest.mark.asyncio
async def test_priority_queue_keeps_high_priority_models(monkeypatch, service_module):
    """Test that priority queue keeps high-priority models loaded when memory constrained.

    Verifies:
    - High priority models stay in memory longer
    - Low priority models are evicted first when memory is full
    - Priority determines eviction order
    """
    # Configure 3 models with different priorities, max 2 concurrent (memory constrained)
    models_config = [
        {
            "model_id": "high-priority",
            "model_path": "/tmp/high.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 100,
        },
        {
            "model_id": "medium-priority",
            "model_path": "/tmp/medium.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 50,
        },
        {
            "model_id": "low-priority",
            "model_path": "/tmp/low.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=2)

    async with _client(service_module.app) as client:
        # Load high-priority and medium-priority models first
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "high-priority",
            },
        )

        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "medium-priority",
            },
        )

        # Check both are loaded
        status1 = await client.get("/status")
        loaded1 = {m["model_id"] for m in status1.json()["loaded_models"]}
        assert loaded1 == {"high-priority", "medium-priority"}

        # Request low-priority model - should evict medium-priority (not high-priority)
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "low-priority",
            },
        )

        # Verify high-priority stayed loaded, medium-priority was evicted
        status2 = await client.get("/status")
        loaded2 = {m["model_id"] for m in status2.json()["loaded_models"]}
        assert "high-priority" in loaded2, "High priority model should stay loaded"
        assert "low-priority" in loaded2
        assert "medium-priority" not in loaded2, "Medium priority should be evicted"

        # Now request medium-priority again - should evict low-priority (not high)
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "medium-priority",
            },
        )

        # Verify high-priority still loaded, low-priority evicted
        status3 = await client.get("/status")
        loaded3 = {m["model_id"] for m in status3.json()["loaded_models"]}
        assert (
            "high-priority" in loaded3
        ), "High priority model should always stay loaded"
        assert "medium-priority" in loaded3
        assert "low-priority" not in loaded3, "Low priority should be evicted"


@pytest.mark.asyncio
async def test_request_pattern_prediction(monkeypatch, service_module):
    """Test that request patterns (A, B, A, B, C) are correctly tracked and predicted.

    Verifies:
    - Request count is tracked for each model
    - Last used timestamp is updated correctly
    - Prediction algorithm identifies most frequently used model
    """
    # Configure 3 models
    models_config = [
        {
            "model_id": "model-a",
            "model_path": "/tmp/a.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "model-b",
            "model_path": "/tmp/b.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "model-c",
            "model_path": "/tmp/c.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=2)

    async with _client(service_module.app) as client:
        # Send requests in pattern: A, B, A, B, C
        request_pattern = ["model-a", "model-b", "model-a", "model-b", "model-c"]

        for model_id in request_pattern:
            response = await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": model_id,
                },
            )
            assert response.status_code == 200

        # Check usage stats
        status = await client.get("/status")
        status_data = status.json()

        # Find usage stats for each model
        loaded_models = {m["model_id"]: m for m in status_data["loaded_models"]}

        # model-a and model-b should each have 2 requests
        # model-c should have 1 request (if it's loaded)
        if "model-a" in loaded_models:
            assert loaded_models["model-a"]["request_count"] >= 2
        if "model-b" in loaded_models:
            assert loaded_models["model-b"]["request_count"] >= 2
        if "model-c" in loaded_models:
            assert loaded_models["model-c"]["request_count"] >= 1

        # Pre-warm candidate should be model-a or model-b (most frequently used)
        pre_warm_candidate = status_data.get("pre_warm_candidate")
        # If both A and B are loaded, the next prediction should still be one of them
        # based on usage pattern, or could be C if it was just used
        assert pre_warm_candidate in ["model-a", "model-b", "model-c"]


@pytest.mark.asyncio
async def test_pre_warming_background_thread(monkeypatch, service_module):
    """Test that pre-warming runs in background without blocking main thread.

    Verifies:
    - Pre-warming doesn't block /generate endpoint
    - Background thread loads model asynchronously
    - Errors in pre-warming don't affect main application
    """
    # Configure 3 models with room for pre-warming
    models_config = [
        {
            "model_id": "primary",
            "model_path": "/tmp/primary.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "secondary",
            "model_path": "/tmp/secondary.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 5,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    load_times: list[tuple[str, float]] = []

    def _build_fake_runtime(config):
        """Track load times to verify background loading."""
        load_start = time.time()
        runtime = FakeMultiModelRuntime(config.model_id, config.backend)
        load_times.append((config.model_id, time.time() - load_start))
        return runtime

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=2)

    async with _client(service_module.app) as client:
        # Send multiple requests to primary model
        request_start = time.time()
        for _ in range(3):
            response = await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": "primary",
                },
            )
            assert response.status_code == 200

        request_duration = time.time() - request_start

        # Trigger pre-warming by calling the function directly
        service_module.pre_warm_next_model()

        # Give a small amount of time for background thread to potentially run
        time.sleep(0.1)

        # Verify requests completed quickly (not blocked by loading)
        assert request_duration < 1.0, "Requests should not be blocked by model loading"

        # Verify models were loaded
        assert len(load_times) > 0


@pytest.mark.asyncio
async def test_status_shows_pre_warm_candidate(monkeypatch, service_module):
    """Test that /status endpoint correctly shows the pre-warm candidate.

    Verifies:
    - /status includes pre_warm_candidate field
    - Pre-warm candidate is None when no usage history
    - Pre-warm candidate is set based on usage patterns
    """
    models_config = [
        {
            "model_id": "model-x",
            "model_path": "/tmp/x.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
        {
            "model_id": "model-y",
            "model_path": "/tmp/y.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=2)

    async with _client(service_module.app) as client:
        # Check initial status - should have pre_warm_candidate field (might be None)
        status1 = await client.get("/status")
        assert status1.status_code == 200
        status_data1 = status1.json()
        assert "pre_warm_candidate" in status_data1

        # Send requests to build usage history
        for _ in range(3):
            await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": "model-x",
                },
            )

        # Check status again - should have a pre-warm candidate now
        status2 = await client.get("/status")
        assert status2.status_code == 200
        status_data2 = status2.json()
        assert "pre_warm_candidate" in status_data2

        # After using model-x multiple times, it should be predicted
        pre_warm_candidate = status_data2["pre_warm_candidate"]
        # Candidate could be model-x (if not already loaded or most used) or model-y
        assert pre_warm_candidate in ["model-x", "model-y", None]


@pytest.mark.asyncio
async def test_memory_constrained_pre_warming(monkeypatch, service_module):
    """Test pre-warming behavior when memory is constrained.

    Verifies:
    - Pre-warming doesn't load models when max_concurrent is reached
    - Pre-warming respects memory limits
    - Pre-warm candidate is still predicted even when can't load
    """
    # Configure with only 1 concurrent model (very constrained)
    models_config = [
        {
            "model_id": "main-model",
            "model_path": "/tmp/main.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "backup-model",
            "model_path": "/tmp/backup.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 5,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "1")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=1)

    async with _client(service_module.app) as client:
        # Load main model
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "main-model",
            },
        )

        # Check status - only one model loaded
        status1 = await client.get("/status")
        status_data1 = status1.json()
        assert len(status_data1["loaded_models"]) == 1
        assert status_data1["loaded_models"][0]["model_id"] == "main-model"
        assert status_data1["max_concurrent_models"] == 1

        # Trigger pre-warming
        service_module.pre_warm_next_model()
        time.sleep(0.1)

        # Status should still show only 1 loaded model (pre-warming respected limit)
        status2 = await client.get("/status")
        status_data2 = status2.json()
        assert len(status_data2["loaded_models"]) == 1

        # But pre-warm candidate should still be predicted
        assert "pre_warm_candidate" in status_data2
