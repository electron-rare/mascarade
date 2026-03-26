"""OpenAI-compatible proxy for mascarade STT (Whisper), TTS (Piper/Wyoming), and LLM (Ollama).

Routes:
  /v1/audio/transcriptions -> mascarade-stt (Whisper ASR)
  /v1/audio/speech         -> mascarade-tts (Piper via Wyoming protocol)
  /v1/models               -> merged list from Ollama + whisper-1 + tts-1
  /v1/*                    -> mascarade-ollama (passthrough for chat, completions, etc.)
  /health                  -> health check
"""

import asyncio
import io
import wave

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize

app = FastAPI(title="mascarade-openai-proxy")

STT_URL = "http://mascarade-stt:9000"
TTS_HOST = "mascarade-tts"
TTS_PORT = 10200
OLLAMA_URL = "http://mascarade-ollama:11434"


# ─── Wyoming TTS ─────────────────────────────────────────────────────────────


async def wyoming_tts_synthesize(text: str) -> bytes:
    """Send a synthesize request via Wyoming protocol and return WAV audio."""
    reader, writer = await asyncio.open_connection(TTS_HOST, TTS_PORT)
    try:
        synth = Synthesize(text=text)
        await async_write_event(synth.event(), writer)

        audio_chunks: list[bytes] = []
        sample_rate = 22050
        sample_width = 2
        channels = 1

        while True:
            event = await asyncio.wait_for(async_read_event(reader), timeout=60)
            if event is None:
                break
            if event.type == "audio-start":
                data = event.data
                if isinstance(data, dict):
                    sample_rate = data.get("rate", sample_rate)
                    sample_width = data.get("width", sample_width)
                    channels = data.get("channels", channels)
            elif event.type == "audio-chunk":
                audio_chunks.append(event.payload)
            elif event.type == "audio-stop":
                break

        raw_audio = b"".join(audio_chunks)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_audio)
        return wav_buf.getvalue()
    finally:
        writer.close()
        await writer.wait_closed()


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    """Merge Ollama models with STT/TTS models."""
    extra_models = [
        {"id": "whisper-1", "object": "model", "owned_by": "mascarade", "created": 0},
        {"id": "tts-1", "object": "model", "owned_by": "mascarade", "created": 0},
        {"id": "tts-1-hd", "object": "model", "owned_by": "mascarade", "created": 0},
    ]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                models.extend(extra_models)
                return {"object": "list", "data": models}
    except Exception:
        pass
    return {"object": "list", "data": extra_models}


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str = Form("fr"),
    response_format: str = Form("json"),
):
    audio_bytes = await file.read()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{STT_URL}/asr",
            params={"task": "transcribe", "language": language, "output": "json"},
            files={
                "audio_file": (
                    file.filename or "audio.wav",
                    audio_bytes,
                    file.content_type or "audio/wav",
                )
            },
        )
    if resp.status_code != 200:
        return JSONResponse(status_code=resp.status_code, content={"error": resp.text})
    result = resp.json()
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    return {"text": text.strip()}


@app.post("/v1/audio/speech")
async def speech(request: Request):
    body = await request.json()
    text = body.get("input", "")
    if not text:
        return JSONResponse(status_code=400, content={"error": "input is required"})
    try:
        wav_data = await wyoming_tts_synthesize(text)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"TTS error: {e}"})
    return Response(content=wav_data, media_type="audio/wav")


# ─── Ollama passthrough for all other /v1/* endpoints ────────────────────────


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def ollama_proxy(request: Request, path: str):
    """Forward any unmatched /v1/* request to Ollama."""
    target_url = f"{OLLAMA_URL}/v1/{path}"
    async with httpx.AsyncClient(timeout=300) as client:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        resp = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )

    # For streaming responses, pass through
    excluded = {"content-encoding", "content-length", "transfer-encoding"}
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8901)
