#!/usr/bin/env python3
"""Mascarade Worker Agent — lightweight inference proxy for cluster nodes.

Runs on each worker machine. Exposes:
- GET  /health        → resource metrics (VRAM, CPU, RAM, loaded models)
- POST /v1/chat/completions → forwards to local runtime (MLX-LM, Ollama, vLLM)

Usage:
    python worker_agent.py --port 8201 --runtime auto
    python worker_agent.py --port 8201 --runtime ollama --ollama-url http://localhost:11434
    python worker_agent.py --port 8201 --runtime mlx_lm --mlx-url http://localhost:8201
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import time

import httpx
import psutil
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mascarade Worker Agent")

# Global state
_runtime: str = "unknown"
_runtime_url: str = ""
_client: httpx.AsyncClient | None = None
_start_time: float = time.time()
_node_id: str = platform.node()


def _detect_runtime() -> tuple[str, str]:
    """Auto-detect the local inference runtime."""
    # Check MLX-LM
    try:
        import mlx_lm  # noqa: F401
        return "mlx_lm", "http://localhost:8201"
    except ImportError:
        pass

    # Check Ollama
    if shutil.which("ollama"):
        return "ollama", "http://localhost:11434"

    # Check vLLM
    try:
        import vllm  # noqa: F401
        return "vllm", "http://localhost:8000"
    except ImportError:
        pass

    return "unknown", ""


def _get_vram_info() -> tuple[int, int]:
    """Get VRAM total/free in MB. Works for NVIDIA and Apple Silicon."""
    # NVIDIA
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return int(parts[0]), int(parts[1])
    except (FileNotFoundError, subprocess.TimeoutExpired, (ValueError, IndexError)):
        pass

    # Apple Silicon — unified memory, report as VRAM
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        total = psutil.virtual_memory().total // (1024 * 1024)
        free = psutil.virtual_memory().available // (1024 * 1024)
        return total, free

    return 0, 0


async def _get_loaded_models() -> list[str]:
    """Get list of models currently loaded in the runtime."""
    if _client is None:
        return []

    try:
        if _runtime == "ollama":
            resp = await _client.get(f"{_runtime_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        elif _runtime in ("mlx_lm", "vllm"):
            resp = await _client.get(f"{_runtime_url}/v1/models", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
    except Exception:
        pass
    return []


@app.on_event("startup")
async def startup():
    global _client
    _client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))


@app.on_event("shutdown")
async def shutdown():
    if _client:
        await _client.aclose()


@app.get("/health")
async def health():
    vram_total, vram_free = _get_vram_info()
    mem = psutil.virtual_memory()
    loaded = await _get_loaded_models()

    return {
        "node_id": _node_id,
        "runtime": _runtime,
        "status": "alive",
        "uptime_s": int(time.time() - _start_time),
        "vram_total_mb": vram_total,
        "vram_free_mb": vram_free,
        "ram_total_mb": mem.total // (1024 * 1024),
        "ram_free_mb": mem.available // (1024 * 1024),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "gpu_percent": 0.0,  # TODO: per-runtime GPU util
        "loaded_models": loaded,
        "max_concurrent": 4 if _runtime == "vllm" else 1,
        "supports_batching": _runtime == "vllm",
        "max_batch_size": 8 if _runtime == "vllm" else 1,
        "max_context_length": 8192,
        "platform": platform.system(),
        "arch": platform.machine(),
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Forward to local runtime."""
    if _client is None:
        return {"error": "Client not initialized"}, 500

    body = await request.json()
    stream = body.get("stream", False)

    # Build target URL
    if _runtime == "ollama":
        target = f"{_runtime_url}/v1/chat/completions"
    else:
        target = f"{_runtime_url}/v1/chat/completions"

    if stream:
        async def stream_proxy():
            async with _client.stream("POST", target, json=body) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

        return StreamingResponse(stream_proxy(), media_type="text/event-stream")
    else:
        resp = await _client.post(target, json=body)
        return resp.json()


def main():
    global _runtime, _runtime_url, _node_id

    parser = argparse.ArgumentParser(description="Mascarade Worker Agent")
    parser.add_argument("--port", type=int, default=8201)
    parser.add_argument("--runtime", default="auto", choices=["auto", "mlx_lm", "ollama", "vllm", "llama_cpp"])
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--mlx-url", default="http://localhost:8201")
    parser.add_argument("--vllm-url", default="http://localhost:8000")
    parser.add_argument("--node-id", default=None)
    args = parser.parse_args()

    if args.node_id:
        _node_id = args.node_id

    if args.runtime == "auto":
        _runtime, _runtime_url = _detect_runtime()
    else:
        _runtime = args.runtime
        _runtime_url = {
            "ollama": args.ollama_url,
            "mlx_lm": args.mlx_url,
            "vllm": args.vllm_url,
            "llama_cpp": args.ollama_url,
        }.get(args.runtime, "")

    print(f"Worker Agent starting: node={_node_id} runtime={_runtime} url={_runtime_url}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
