#!/usr/bin/env python3
"""Local audio generation API service (AudioGen/MusicGen)."""

from __future__ import annotations

import os
from io import BytesIO
from threading import Lock

import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Mascarade Generate Audio", version="0.1.0")


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=400)
    duration: float = Field(default=5.0, ge=1.0, le=30.0)
    seed: int | None = Field(default=None, ge=0)
    model: str | None = Field(default=None)


_model_lock = Lock()
_loaded = {"engine": None, "model": None, "device": None, "obj": None}


def _sanitize_choice(raw: str | None, allowed: set[str], default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in allowed:
        return default
    return value


def _resolve_runtime() -> str:
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

        _loaded.update(
            {"engine": engine, "model": model_name, "device": device, "obj": model}
        )
        return model


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "cuda_available": torch.cuda.is_available(),
        "loaded_engine": _loaded["engine"],
        "loaded_model": _loaded["model"],
        "loaded_device": _loaded["device"],
    }


@app.post("/generate")
def generate(req: GenerateRequest):
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
    return StreamingResponse(buf, media_type="audio/wav", headers=headers)
