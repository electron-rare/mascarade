#!/usr/bin/env python3
"""Runtime helpers for deploying and smoking Ollama models."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_OLLAMA_CONTAINER = "mascarade-ollama"
DEFAULT_OLLAMA_STORE_DEST = "/root/.ollama"
DEFAULT_DEPLOY_MODE = "auto"
DEPLOY_MODE_ENV = "MASCARADE_OLLAMA_DEPLOY_MODE"


class OllamaRuntimeError(RuntimeError):
    """Raised when no usable Ollama deployment target can be resolved."""


def _combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    return ((completed.stdout or "") + (completed.stderr or "")).strip()


def _run_command(
    command: list[str],
    *,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _failed_process(command: list[str], message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        command,
        1,
        stdout="",
        stderr=message,
    )


def probe_host_ollama() -> tuple[bool, str]:
    if shutil.which("ollama") is None:
        return False, "host ollama CLI not found"
    completed = _run_command(["ollama", "list"], timeout=30)
    if completed.returncode == 0:
        return True, "host Ollama CLI and daemon are healthy"
    return False, _combined_output(completed) or "host Ollama list failed"


def inspect_container_mounts(container: str = DEFAULT_OLLAMA_CONTAINER) -> tuple[bool, str, list[dict[str, str | bool]]]:
    completed = _run_command(
        [
            "docker",
            "inspect",
            container,
            "--format",
            "{{range .Mounts}}{{println .Destination .Source .RW}}{{end}}",
        ],
        timeout=30,
    )
    if completed.returncode != 0:
        return False, _combined_output(completed) or f"docker inspect failed for {container}", []

    mounts: list[dict[str, str | bool]] = []
    for raw_line in (completed.stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        destination, source, rw = parts[0], parts[1], parts[2].lower() == "true"
        mounts.append({"destination": destination, "source": source, "rw": rw})
    return True, "container is inspectable", mounts


def probe_container_ollama(container: str = DEFAULT_OLLAMA_CONTAINER) -> tuple[bool, str, dict]:
    ok, reason, mounts = inspect_container_mounts(container)
    if not ok:
        return False, reason, {"store_readonly": None, "mounts": mounts}

    store_mount = next(
        (mount for mount in mounts if mount.get("destination") == DEFAULT_OLLAMA_STORE_DEST),
        None,
    )
    store_readonly = False
    if store_mount is not None:
        store_readonly = not bool(store_mount.get("rw"))

    if store_mount is None:
        return True, "container is available and uses its own writable store", {
            "store_readonly": False,
            "mounts": mounts,
        }
    if store_readonly:
        return True, "container store is mounted read-only", {
            "store_readonly": True,
            "mounts": mounts,
        }
    return True, "container store is writable", {"store_readonly": False, "mounts": mounts}


def resolve_ollama_runtime(
    mode: str | None = None,
    *,
    container: str = DEFAULT_OLLAMA_CONTAINER,
) -> dict:
    requested_mode = (mode or os.getenv(DEPLOY_MODE_ENV, DEFAULT_DEPLOY_MODE)).strip().lower()
    if requested_mode not in {"auto", "host", "container"}:
        raise OllamaRuntimeError(
            f"unsupported Ollama deploy mode '{requested_mode}' "
            f"(expected auto, host or container)"
        )

    host_ok, host_reason = probe_host_ollama()
    container_ok, container_reason, container_meta = probe_container_ollama(container)
    store_readonly = bool(container_meta.get("store_readonly"))

    if requested_mode == "host":
        if not host_ok:
            raise OllamaRuntimeError(f"forced host mode but host Ollama is unavailable: {host_reason}")
        return {
            "mode": "host",
            "reason": host_reason,
            "container": container,
            "container_store_readonly": store_readonly,
        }

    if requested_mode == "container":
        if not container_ok:
            raise OllamaRuntimeError(
                f"forced container mode but Ollama container is unavailable: {container_reason}"
            )
        if store_readonly:
            raise OllamaRuntimeError(
                f"forced container mode but {container} uses a read-only model store"
            )
        return {
            "mode": "container",
            "reason": container_reason,
            "container": container,
            "container_store_readonly": store_readonly,
        }

    if host_ok:
        reason = "using host Ollama automatically"
        if container_ok and store_readonly:
            reason += f" because {container} uses a read-only store"
        elif container_ok:
            reason += " because host Ollama is healthy"
        else:
            reason += f" because the container path is unavailable ({container_reason})"
        return {
            "mode": "host",
            "reason": reason,
            "container": container,
            "container_store_readonly": store_readonly,
        }

    if container_ok and not store_readonly:
        return {
            "mode": "container",
            "reason": "using writable Ollama container automatically",
            "container": container,
            "container_store_readonly": store_readonly,
        }

    if container_ok and store_readonly:
        raise OllamaRuntimeError(
            f"host Ollama is unavailable ({host_reason}) and {container} uses a read-only model store"
        )

    raise OllamaRuntimeError(
        f"no usable Ollama runtime found (host: {host_reason}; container: {container_reason})"
    )


def create_model(
    runtime: dict,
    *,
    model_name: str,
    modelfile_path: Path,
    gguf_path: Path,
) -> subprocess.CompletedProcess[str]:
    if runtime["mode"] == "host":
        return _run_command(["ollama", "create", model_name, "-f", str(modelfile_path)], timeout=900)

    container = str(runtime["container"])
    copy_model = _run_command(
        ["docker", "cp", str(gguf_path), f"{container}:/tmp/{gguf_path.name}"], timeout=300
    )
    if copy_model.returncode != 0:
        return _failed_process(copy_model.args, _combined_output(copy_model) or "docker cp GGUF failed")
    copy_modelfile = _run_command(
        ["docker", "cp", str(modelfile_path), f"{container}:/tmp/Modelfile"], timeout=300
    )
    if copy_modelfile.returncode != 0:
        return _failed_process(
            copy_modelfile.args,
            _combined_output(copy_modelfile) or "docker cp Modelfile failed",
        )
    rewrite_from = _run_command(
        [
            "docker",
            "exec",
            container,
            "sed",
            "-i",
            f"s|FROM .*|FROM /tmp/{gguf_path.name}|",
            "/tmp/Modelfile",
        ],
        timeout=60,
    )
    if rewrite_from.returncode != 0:
        return _failed_process(
            rewrite_from.args,
            _combined_output(rewrite_from) or "failed to rewrite Modelfile inside container",
        )
    return _run_command(
        ["docker", "exec", container, "ollama", "create", model_name, "-f", "/tmp/Modelfile"],
        timeout=900,
    )


def run_model(
    runtime: dict,
    *,
    model_name: str,
    prompt: str,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    if runtime["mode"] == "host":
        return _run_command(["ollama", "run", model_name, prompt], timeout=timeout)
    container = str(runtime["container"])
    return _run_command(
        ["docker", "exec", container, "ollama", "run", model_name, prompt],
        timeout=timeout,
    )
