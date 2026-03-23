"""End-to-end tests for Apple LLM multi-model serving."""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import httpx
import pytest

SERVICE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "apple_llm_api" / "app.py"
)


def _load_service_module():
    """Load the Apple LLM service module for testing."""
    spec = spec_from_file_location("test_e2e_apple_multi_model_app", SERVICE_PATH)
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
async def test_concurrent_model_serving(monkeypatch, service_module):
    """Test concurrent serving of multiple models when memory allows.

    Verifies:
    - Multiple models can be loaded simultaneously
    - Each model responds correctly
    - /status endpoint reflects loaded models
    - Max concurrent models is respected
    """
    # Configure multi-model setup with 2 concurrent models allowed
    models_config = [
        {
            "model_id": "apple-4b",
            "model_path": "/tmp/model-4b.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
        {
            "model_id": "apple-0.5b",
            "model_path": "/tmp/model-0.5b.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 2,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "2")

    # Track which models were built
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
        # Send request for model A
        response_a = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "hello from A"}],
                "model": "apple-4b",
            },
        )
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert data_a["content"] == "Response from apple-4b"
        assert data_a["model"] == "apple-4b"

        # Send request for model B
        response_b = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "hello from B"}],
                "model": "apple-0.5b",
            },
        )
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert data_b["content"] == "Response from apple-0.5b"
        assert data_b["model"] == "apple-0.5b"

        # Check /status endpoint
        status_response = await client.get("/status")
        assert status_response.status_code == 200
        status = status_response.json()

        # Verify both models are loaded (concurrent serving)
        assert status["max_concurrent_models"] == 2
        loaded_model_ids = [m["model_id"] for m in status["loaded_models"]]
        assert "apple-4b" in loaded_model_ids
        assert "apple-0.5b" in loaded_model_ids
        assert len(loaded_model_ids) == 2

        # Verify usage tracking
        model_4b_info = next(
            m for m in status["loaded_models"] if m["model_id"] == "apple-4b"
        )
        model_05b_info = next(
            m for m in status["loaded_models"] if m["model_id"] == "apple-0.5b"
        )
        assert model_4b_info["request_count"] >= 1
        assert model_05b_info["request_count"] >= 1
        assert model_4b_info["priority"] == 1
        assert model_05b_info["priority"] == 2


@pytest.mark.asyncio
async def test_hot_swap_when_memory_constrained(monkeypatch, service_module):
    """Test hot-swap behavior when only one model can be loaded at a time.

    Verifies:
    - Model A loads and responds
    - Request for model B triggers hot-swap (unload A, load B)
    - Swap completes successfully
    - /status shows only the currently loaded model
    - Priority determines which model is evicted
    """
    # Configure multi-model setup with only 1 concurrent model (memory constrained)
    models_config = [
        {
            "model_id": "apple-large",
            "model_path": "/tmp/model-large.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
        {
            "model_id": "apple-small",
            "model_path": "/tmp/model-small.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 2,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "1")

    built_models: dict[str, FakeMultiModelRuntime] = {}
    unloaded_models: list[str] = []

    def _build_fake_runtime(config):
        runtime = FakeMultiModelRuntime(config.model_id, config.backend)
        built_models[config.model_id] = runtime
        return runtime

    # Track model unloading
    original_unload = service_module.ModelManager.unload_model

    def _tracked_unload(self, model_id: str) -> None:
        unloaded_models.append(model_id)
        return original_unload(self, model_id)

    monkeypatch.setattr(service_module.ModelManager, "unload_model", _tracked_unload)
    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)

    # Reload the global model manager with new config
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=1)

    async with _client(service_module.app) as client:
        # Send request for model A
        start_time = time.time()
        response_a = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test A"}],
                "model": "apple-large",
            },
        )
        assert response_a.status_code == 200
        assert response_a.json()["content"] == "Response from apple-large"

        # Check status - only model A should be loaded
        status_1 = await client.get("/status")
        assert status_1.status_code == 200
        loaded_1 = [m["model_id"] for m in status_1.json()["loaded_models"]]
        assert loaded_1 == ["apple-large"]

        # Send request for model B (should trigger hot-swap)
        response_b = await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test B"}],
                "model": "apple-small",
            },
        )
        swap_time = time.time() - start_time

        assert response_b.status_code == 200
        assert response_b.json()["content"] == "Response from apple-small"

        # Verify swap completed in <30s
        assert swap_time < 30.0, f"Model swap took {swap_time:.1f}s, expected <30s"

        # Check status - only model B should be loaded now
        status_2 = await client.get("/status")
        assert status_2.status_code == 200
        loaded_2 = [m["model_id"] for m in status_2.json()["loaded_models"]]
        assert loaded_2 == ["apple-small"]

        # Verify model A was unloaded
        assert "apple-large" in unloaded_models


@pytest.mark.asyncio
async def test_priority_based_eviction(monkeypatch, service_module):
    """Test that priority determines which model is evicted when memory is full.

    Verifies:
    - Higher priority models are kept in memory longer
    - Lower priority models are evicted first
    - Priority queue works correctly across multiple swaps
    """
    # Configure 3 models with different priorities, max 2 concurrent
    models_config = [
        {
            "model_id": "apple-high-priority",
            "model_path": "/tmp/high.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 10,
        },
        {
            "model_id": "apple-medium-priority",
            "model_path": "/tmp/medium.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 5,
        },
        {
            "model_id": "apple-low-priority",
            "model_path": "/tmp/low.mlpackage",
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
        # Load high and medium priority models
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "apple-high-priority",
            },
        )
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "apple-medium-priority",
            },
        )

        # Check both are loaded
        status_1 = await client.get("/status")
        loaded_1 = {m["model_id"] for m in status_1.json()["loaded_models"]}
        assert loaded_1 == {"apple-high-priority", "apple-medium-priority"}

        # Request low priority model - should evict medium (not high)
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "apple-low-priority",
            },
        )

        # Check that high-priority stayed, medium was evicted
        status_2 = await client.get("/status")
        loaded_2 = {m["model_id"] for m in status_2.json()["loaded_models"]}
        assert (
            "apple-high-priority" in loaded_2
        ), "High priority model should not be evicted"
        assert "apple-low-priority" in loaded_2
        assert (
            "apple-medium-priority" not in loaded_2
        ), "Medium priority should be evicted first"


@pytest.mark.asyncio
async def test_model_list_endpoint(monkeypatch, service_module):
    """Test /models endpoint returns all configured models with status.

    Verifies:
    - All configured models are listed
    - Loaded status is correct for each model
    - Priority and backend info are included
    """
    models_config = [
        {
            "model_id": "model-a",
            "model_path": "/tmp/a.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
        {
            "model_id": "model-b",
            "model_path": "/tmp/b.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "mlx",
            "priority": 2,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "1")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=1)

    async with _client(service_module.app) as client:
        # Before loading any model
        response_1 = await client.get("/models")
        assert response_1.status_code == 200
        data_1 = response_1.json()

        assert len(data_1["models"]) == 2
        assert data_1["max_concurrent"] == 1
        assert all(not m["loaded"] for m in data_1["models"])

        # Load one model
        await client.post(
            "/generate",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "model": "model-a",
            },
        )

        # Check models list again
        response_2 = await client.get("/models")
        assert response_2.status_code == 200
        data_2 = response_2.json()

        model_a = next(m for m in data_2["models"] if m["model_id"] == "model-a")
        model_b = next(m for m in data_2["models"] if m["model_id"] == "model-b")

        assert model_a["loaded"] is True
        assert model_a["priority"] == 1
        assert model_a["backend"] == "coreml"

        assert model_b["loaded"] is False
        assert model_b["priority"] == 2
        assert model_b["backend"] == "mlx"


@pytest.mark.asyncio
async def test_usage_tracking_across_requests(monkeypatch, service_module):
    """Test that usage statistics are tracked correctly across multiple requests.

    Verifies:
    - Request count increments correctly
    - Last used timestamp updates
    - Usage stats are visible in /status endpoint
    """
    models_config = [
        {
            "model_id": "tracked-model",
            "model_path": "/tmp/tracked.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=1)

    async with _client(service_module.app) as client:
        # Send multiple requests
        for i in range(3):
            response = await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": f"request {i}"}],
                    "model": "tracked-model",
                },
            )
            assert response.status_code == 200

        # Check usage stats
        status = await client.get("/status")
        assert status.status_code == 200
        data = status.json()

        model_info = data["loaded_models"][0]
        assert model_info["model_id"] == "tracked-model"
        assert model_info["request_count"] >= 3  # At least 3 requests tracked
        assert model_info["last_used"] is not None
        assert isinstance(model_info["last_used"], (int, float))


@pytest.mark.asyncio
async def test_swap_performance_benchmark(monkeypatch, service_module):
    """Benchmark test to ensure model swap meets <30s performance target.

    Verifies:
    - Model swap under memory constraint completes in <30s
    - Multiple swaps maintain acceptable performance
    """
    models_config = [
        {
            "model_id": "model-1",
            "model_path": "/tmp/1.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 1,
        },
        {
            "model_id": "model-2",
            "model_path": "/tmp/2.mlpackage",
            "tokenizer_path": "/tmp/tokenizer",
            "backend": "coreml",
            "priority": 2,
        },
    ]
    monkeypatch.setenv("APPLE_LLM_MODELS_JSON", str(models_config).replace("'", '"'))
    monkeypatch.setenv("APPLE_LLM_MAX_CONCURRENT_MODELS", "1")

    def _build_fake_runtime(config):
        return FakeMultiModelRuntime(config.model_id, config.backend)

    monkeypatch.setattr(service_module, "_build_runtime", _build_fake_runtime)
    service_module._model_manager = service_module.ModelManager(max_concurrent_models=1)

    async with _client(service_module.app) as client:
        swap_times = []

        # Perform 3 swaps and measure time
        for i in range(3):
            model_id = "model-1" if i % 2 == 0 else "model-2"
            start = time.time()

            response = await client.post(
                "/generate",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": model_id,
                },
            )

            elapsed = time.time() - start
            swap_times.append(elapsed)

            assert response.status_code == 200

        # Verify all swaps were fast (with fake runtime, should be near-instant)
        # In real scenario with actual models, this ensures <30s target
        for i, swap_time in enumerate(swap_times):
            assert swap_time < 30.0, f"Swap {i} took {swap_time:.1f}s, expected <30s"

        # Average should be much faster with fake runtime
        avg_swap_time = sum(swap_times) / len(swap_times)
        assert (
            avg_swap_time < 1.0
        ), f"Average swap time {avg_swap_time:.1f}s should be <1s with fake runtime"
