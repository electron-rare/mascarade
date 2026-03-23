"""HTTP tests for the standalone generate-audio FastAPI service."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from fastapi import HTTPException

SERVICE_PATH = Path(__file__).resolve().parents[2] / "deploy" / "audio_gen_api" / "app.py"


def _load_service_module():
    spec = spec_from_file_location("test_generate_audio_service_app", SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
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


class _FakeCuda:
    def __init__(self, available: bool):
        self._available = available
        self.seed = None
        self.cache_cleared = False

    def is_available(self) -> bool:
        return self._available

    def manual_seed_all(self, seed: int) -> None:
        self.seed = seed

    def empty_cache(self) -> None:
        self.cache_cleared = True


class _FakeTorch:
    def __init__(self, cuda_available: bool):
        self.cuda = _FakeCuda(cuda_available)
        self.seed = None

    def manual_seed(self, seed: int) -> None:
        self.seed = seed


class _FakeTensor:
    def __init__(self, dims: int = 1):
        self._dims = dims

    def detach(self):
        return self

    def cpu(self):
        return self

    def dim(self) -> int:
        return self._dims

    def unsqueeze(self, _: int):
        self._dims += 1
        return self


class _FakeTorchaudio:
    def __init__(self):
        self.saved = []

    def save(self, buffer, audio, sample_rate: int, format: str = "wav") -> None:
        self.saved.append((sample_rate, format, audio.dim()))
        buffer.write(b"RIFF\x00\x00\x00\x00WAVEfmt ")


class _FakeModel:
    def __init__(self, model_name: str, device: str, wav=None):
        self.model_name = model_name
        self.device = device
        self.sample_rate = 32000
        self.evaluated = False
        self.params = []
        self.prompts = []
        self._wav = [*_ensure_wav(wav)]

    def to(self, device: str):
        self.device = device
        return self

    def eval(self) -> None:
        self.evaluated = True

    def set_generation_params(self, duration: float) -> None:
        self.params.append(duration)

    def generate(self, prompts: list[str]):
        self.prompts = prompts
        return self._wav


def _ensure_wav(wav):
    if wav is None:
        return [_FakeTensor()]
    return wav


def _install_fake_audiocraft(monkeypatch, registry: dict, wav=None) -> None:
    audiocraft_module = ModuleType("audiocraft")
    models_module = ModuleType("audiocraft.models")

    class AudioGen:
        @staticmethod
        def get_pretrained(model_name: str, device: str):
            model = _FakeModel(model_name, device, wav=wav)
            registry["AudioGen"] = model
            return model

    class MusicGen:
        @staticmethod
        def get_pretrained(model_name: str, device: str):
            model = _FakeModel(model_name, device, wav=wav)
            registry["MusicGen"] = model
            return model

    models_module.AudioGen = AudioGen
    models_module.MusicGen = MusicGen
    audiocraft_module.models = models_module

    monkeypatch.setitem(sys.modules, "audiocraft", audiocraft_module)
    monkeypatch.setitem(sys.modules, "audiocraft.models", models_module)


@pytest.fixture
def service_module():
    return _load_service_module()


@pytest.mark.asyncio
async def test_health_reports_runtime_readiness(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=True)
    fake_torchaudio = _FakeTorchaudio()
    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setattr(service_module, "_package_version", lambda name: f"{name}-test")

    async with _client(service_module.app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "runtime_ready": True,
        "runtime_error": None,
        "cuda_available": True,
        "torch_version": "torch-test",
        "torchaudio_version": "torchaudio-test",
        "audiocraft_version": "audiocraft-test",
        "torch_variant": "cpu",
        "model_loaded": False,
        "loaded_engine": None,
        "loaded_model": None,
        "loaded_device": None,
        "keep_loaded": False,
        "idle_unload_seconds": 0,
        "inflight_requests": 0,
    }


@pytest.mark.asyncio
async def test_health_reports_runtime_failures(monkeypatch, service_module):
    def _raise_runtime_error():
        raise HTTPException(status_code=503, detail="deps missing")

    monkeypatch.setattr(service_module, "_import_torch_stack", _raise_runtime_error)

    async with _client(service_module.app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["runtime_ready"] is False
    assert response.json()["runtime_error"] == "deps missing"
    assert response.json()["model_loaded"] is False
    assert response.json()["keep_loaded"] is False
    assert response.json()["idle_unload_seconds"] == 0
    assert response.json()["inflight_requests"] == 0


@pytest.mark.asyncio
async def test_generate_returns_wav_for_audiogen(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=False)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setenv("GENERATE_AUDIO_ENGINE", "audiogen")
    monkeypatch.setenv("GENERATE_AUDIO_MODEL", "facebook/audiogen-medium")
    monkeypatch.setenv("GENERATE_AUDIO_RUNTIME", "cpu")
    _install_fake_audiocraft(monkeypatch, registry)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "hello world", "duration": 1.0},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-audio-engine"] == "audiogen"
    assert response.headers["x-audio-model"] == "facebook/audiogen-medium"
    assert response.headers["x-audio-device"] == "cpu"
    assert response.content.startswith(b"RIFF")
    assert registry["AudioGen"].params == [1.0]
    assert registry["AudioGen"].prompts == ["hello world"]
    assert service_module._loaded["obj"] is None


@pytest.mark.asyncio
async def test_generate_uses_musicgen_defaults(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=False)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setenv("GENERATE_AUDIO_ENGINE", "musicgen")
    monkeypatch.delenv("GENERATE_AUDIO_MODEL", raising=False)
    monkeypatch.setenv("GENERATE_AUDIO_RUNTIME", "cpu")
    _install_fake_audiocraft(monkeypatch, registry)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "drum loop", "duration": 1.0},
        )

    assert response.status_code == 200
    assert response.headers["x-audio-engine"] == "musicgen"
    assert response.headers["x-audio-model"] == "facebook/musicgen-small"
    assert registry["MusicGen"].model_name == "facebook/musicgen-small"


@pytest.mark.asyncio
async def test_generate_falls_back_to_cpu_when_cuda_unavailable(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=False)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setenv("GENERATE_AUDIO_RUNTIME", "cuda")
    _install_fake_audiocraft(monkeypatch, registry)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "soft pad", "duration": 1.0},
        )

    assert response.status_code == 200
    assert response.headers["x-audio-device"] == "cpu"
    assert registry["AudioGen"].device == "cpu"


@pytest.mark.asyncio
async def test_generate_keeps_model_loaded_when_enabled(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=False)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setenv("GENERATE_AUDIO_KEEP_LOADED", "true")
    _install_fake_audiocraft(monkeypatch, registry)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "keep warm", "duration": 1.0},
        )

    assert response.status_code == 200
    assert service_module._loaded["obj"] is registry["AudioGen"]
    assert service_module._loaded["inflight"] == 0


@pytest.mark.asyncio
async def test_unload_endpoint_clears_loaded_model(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=True)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    monkeypatch.setenv("GENERATE_AUDIO_KEEP_LOADED", "true")
    _install_fake_audiocraft(monkeypatch, registry)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "clear cache", "duration": 1.0},
        )
        assert response.status_code == 200
        assert service_module._loaded["obj"] is registry["AudioGen"]

        unload_response = await client.post("/unload")

    assert unload_response.status_code == 200
    assert unload_response.json() == {"ok": True, "unloaded": True}
    assert service_module._loaded["obj"] is None
    assert fake_torch.cuda.cache_cleared is True


@pytest.mark.asyncio
async def test_generate_returns_503_when_runtime_is_missing(monkeypatch, service_module):
    def _raise_runtime_error():
        raise HTTPException(
            status_code=503,
            detail="Audio runtime dependencies are not available: missing torch",
        )

    monkeypatch.setattr(service_module, "_import_torch_stack", _raise_runtime_error)

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "failure case", "duration": 1.0},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Audio runtime dependencies are not available: missing torch"


@pytest.mark.asyncio
async def test_generate_rejects_empty_audio(monkeypatch, service_module):
    fake_torch = _FakeTorch(cuda_available=False)
    fake_torchaudio = _FakeTorchaudio()
    registry = {}

    monkeypatch.setattr(service_module, "_import_torch_stack", lambda: (fake_torch, fake_torchaudio))
    _install_fake_audiocraft(monkeypatch, registry, wav=[])

    async with _client(service_module.app) as client:
        response = await client.post(
            "/generate",
            json={"prompt": "empty output", "duration": 1.0},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Generation returned empty audio"
