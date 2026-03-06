#!/usr/bin/env python3
"""Local audio generation API service (AudioGen/MusicGen)."""

from __future__ import annotations

import importlib.metadata
import os
from io import BytesIO
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="Mascarade Generate Audio", version="0.1.0")


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=400)
    duration: float = Field(default=5.0, ge=1.0, le=30.0)
    seed: int | None = Field(default=None, ge=0)
    model: str | None = Field(default=None)


_model_lock = Lock()
_loaded = {"engine": None, "model": None, "device": None, "obj": None}


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _import_torch_stack():
    try:
        import torch
        import torchaudio
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=503,
            detail=f"Audio runtime dependencies are not available: {exc}",
        ) from exc
    return torch, torchaudio


def _sanitize_choice(raw: str | None, allowed: set[str], default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in allowed:
        return default
    return value


def _resolve_runtime() -> str:
    torch, _ = _import_torch_stack()
    runtime = _sanitize_choice(
        os.getenv("GENERATE_AUDIO_RUNTIME", "auto"),
        {"auto", "cpu", "cuda"},
        "auto",
    )
    if runtime == "cpu":
        return "cpu"
    if runtime == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _runtime_status() -> tuple[bool, str | None, bool]:
    try:
        torch, _ = _import_torch_stack()
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return False, detail, False
    return True, None, bool(torch.cuda.is_available())


def _resolve_model(engine: str, requested: str | None) -> str:
    if requested:
        return requested
    env_model = os.getenv("GENERATE_AUDIO_MODEL", "").strip()
    if env_model:
        if engine == "musicgen" and "audiogen" in env_model.lower():
            return "facebook/musicgen-small"
        if engine == "audiogen" and "musicgen" in env_model.lower():
            return "facebook/audiogen-medium"
        return env_model
    return (
        "facebook/musicgen-small"
        if engine == "musicgen"
        else "facebook/audiogen-medium"
    )


def _load_model(engine: str, model_name: str, device: str):
    with _model_lock:
        if (
            _loaded["obj"] is not None
            and _loaded["engine"] == engine
            and _loaded["model"] == model_name
            and _loaded["device"] == device
        ):
            return _loaded["obj"]

        try:
            torch, _ = _import_torch_stack()
            if engine == "musicgen":
                from audiocraft.models import MusicGen

                model = MusicGen.get_pretrained(model_name, device=device)
            else:
                from audiocraft.models import AudioGen

                model = AudioGen.get_pretrained(model_name, device=device)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=500, detail=f"Model load failed: {exc}"
            ) from exc

        if hasattr(model, "to"):
            model = model.to(device)
        if hasattr(model, "eval"):
            model.eval()

        _loaded.update(
            {"engine": engine, "model": model_name, "device": device, "obj": model}
        )
        return model


@app.get("/health")
async def health() -> dict:
    torch_version = _package_version("torch")
    torchaudio_version = _package_version("torchaudio")
    audiocraft_version = _package_version("audiocraft")
    runtime_ready, runtime_error, cuda_available = _runtime_status()

    return {
        "ok": True,
        "runtime_ready": runtime_ready,
        "runtime_error": runtime_error,
        "cuda_available": cuda_available,
        "torch_version": torch_version,
        "torchaudio_version": torchaudio_version,
        "audiocraft_version": audiocraft_version,
        "torch_variant": os.getenv("GENERATE_AUDIO_TORCH_VARIANT", "cpu"),
        "model_loaded": _loaded["obj"] is not None,
        "loaded_engine": _loaded["engine"],
        "loaded_model": _loaded["model"],
        "loaded_device": _loaded["device"],
    }


def _generate_response(req: GenerateRequest):
    torch, torchaudio = _import_torch_stack()
    engine = _sanitize_choice(
        os.getenv("GENERATE_AUDIO_ENGINE", "audiogen"),
        {"audiogen", "musicgen"},
        "audiogen",
    )
    device = _resolve_runtime()
    model_name = _resolve_model(engine, req.model)

    model = _load_model(engine, model_name, device)

    if req.seed is not None:
        torch.manual_seed(req.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(req.seed)

    try:
        model.set_generation_params(duration=req.duration)
        wav = model.generate([req.prompt])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail=f"Generation failed: {exc}"
        ) from exc

    if wav is None or len(wav) == 0:
        raise HTTPException(status_code=500, detail="Generation returned empty audio")

    sample_rate = int(getattr(model, "sample_rate", 32000))
    audio = wav[0].detach().cpu()
    if audio.dim() == 1:
        audio = audio.unsqueeze(0)

    buf = BytesIO()
    torchaudio.save(buf, audio, sample_rate, format="wav")
    buf.seek(0)

    headers = {
        "X-Audio-Engine": engine,
        "X-Audio-Model": model_name,
        "X-Audio-Device": device,
    }
    return Response(content=buf.getvalue(), media_type="audio/wav", headers=headers)


@app.post("/generate")
async def generate(req: GenerateRequest):
    return _generate_response(req)
