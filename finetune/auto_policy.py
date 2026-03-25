#!/usr/bin/env python3
"""Hardware-adaptive policy helpers for local fine-tuning batches."""

from __future__ import annotations

import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from llm_paths import configure_hf_env, hf_cache_roots

try:
    from runtime_compat import disable_broken_torchvision

    disable_broken_torchvision()
except Exception:  # pragma: no cover - optional at import time
    pass

try:
    import torch
except Exception:  # pragma: no cover - optional at import time
    torch = None

DEFAULT_OLLAMA_API_URL = "http://127.0.0.1:11434"

_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Bb]")

FULL_GPU_LOCAL_HF_TEACHERS = {
    "qwen/qwen2.5-7b-instruct",
    "qwen/qwen3-4b-instruct-2507",
}

OFFLOAD_LOCAL_HF_TEACHERS = {
    "qwen/qwen3.5-35b-a3b-gptq-int4",
    "mistralai/devstral-small-2-24b-instruct-2512",
    "mistralai/mistral-small-3.1-24b-base-2503",
    "deepseek-ai/deepseek-coder-v2-lite-instruct",
}

MANUAL_ONLY_LOCAL_HF_TEACHERS = {
    "mistralai/mistral-small-3.1-24b-base-2503",
}

CODE_HEAVY_DOMAINS = {
    "stm32",
    "embedded",
    "platformio",
    "iot",
    "kicad",
    "freecad",
}

TEACHER_OBJECTIVES = ("fast", "balanced", "quality")

CURRENT_STUDENT_CANDIDATES = (
    {
        "model": "Qwen/Qwen3.5-9B-Base",
        "role": "student",
        "source": "huggingface",
        "family": "qwen",
        "min_vram_mb": 22000,
        "reason": "current best local student for a single 24 GB class GPU",
    },
    {
        "model": "Qwen/Qwen3-8B",
        "role": "student",
        "source": "huggingface",
        "family": "qwen",
        "min_vram_mb": 18000,
        "reason": "recent dense student with a stable local QLoRA path",
    },
    {
        "model": "Qwen/Qwen3-4B-Instruct-2507",
        "role": "student",
        "source": "huggingface",
        "family": "qwen",
        "min_vram_mb": 12000,
        "reason": "recent dense student optimized for more parallel local runs",
    },
    {
        "model": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "role": "student",
        "source": "huggingface",
        "family": "qwen",
        "min_vram_mb": 6000,
        "reason": "fallback student for constrained GPUs and CPU fallback workflows",
    },
)

TEACHER_CANDIDATE_CATALOG = {
    "local-hf:Qwen/Qwen2.5-7B-Instruct": {
        "provider": "local-hf",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "source": "huggingface",
        "min_vram_mb": 16000,
        "local_hf_device": "cuda:0",
        "gpu_active": True,
        "reason": "validated 7B dense local-hf teacher with true GPU compute on this machine",
    },
    "local-hf:Qwen/Qwen3-4B-Instruct-2507": {
        "provider": "local-hf",
        "model": "Qwen/Qwen3-4B-Instruct-2507",
        "source": "huggingface",
        "min_vram_mb": 12000,
        "local_hf_device": "cuda:0",
        "gpu_active": True,
        "reason": "validated 4B dense local-hf teacher optimized for fast true GPU distillation on this machine",
    },
    "local-hf:Qwen/Qwen3.5-35B-A3B-GPTQ-Int4": {
        "provider": "local-hf",
        "model": "Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        "source": "huggingface",
        "min_vram_mb": 22000,
        "local_hf_device": "auto",
        "gpu_active": True,
        "reason": "latest local Qwen teacher already validated as teacher-only in this pipeline; keep device_map=auto on a single 24 GB GPU",
    },
    "local-hf:mistralai/Devstral-Small-2-24B-Instruct-2512": {
        "provider": "local-hf",
        "model": "mistralai/Devstral-Small-2-24B-Instruct-2512",
        "source": "huggingface",
        "min_vram_mb": 22000,
        "local_hf_device": "auto",
        "gpu_active": True,
        "reason": "newer Devstral 24B local teacher candidate for coding-oriented distillation; prefer device_map=auto on a single 24 GB GPU",
    },
    "local-hf:mistralai/Mistral-Small-3.1-24B-Base-2503": {
        "provider": "local-hf",
        "model": "mistralai/Mistral-Small-3.1-24B-Base-2503",
        "source": "huggingface",
        "min_vram_mb": 22000,
        "local_hf_device": "auto",
        "gpu_active": True,
        "auto_enabled": False,
        "reason": "recent Mistral 24B base checkpoint kept as a local teacher candidate; prefer device_map=auto on a single 24 GB GPU",
    },
    "ollama:qwen2.5:14b": {
        "provider": "ollama",
        "model": "qwen2.5:14b",
        "source": "local-runtime",
        "min_vram_mb": 0,
        "local_hf_device": None,
        "gpu_active": False,
        "reason": "stable local fallback teacher already integrated with Mascarade",
    },
}

TEACHER_CANDIDATE_ORDERS = {
    "fast": (
        "local-hf:Qwen/Qwen3-4B-Instruct-2507",
        "local-hf:Qwen/Qwen2.5-7B-Instruct",
        "ollama:qwen2.5:14b",
        "local-hf:Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        "local-hf:mistralai/Devstral-Small-2-24B-Instruct-2512",
        "local-hf:mistralai/Mistral-Small-3.1-24B-Base-2503",
    ),
    "balanced": (
        "local-hf:Qwen/Qwen2.5-7B-Instruct",
        "local-hf:Qwen/Qwen3-4B-Instruct-2507",
        "local-hf:Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        "ollama:qwen2.5:14b",
        "local-hf:mistralai/Devstral-Small-2-24B-Instruct-2512",
        "local-hf:mistralai/Mistral-Small-3.1-24B-Base-2503",
    ),
    "quality": (
        "local-hf:Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        "local-hf:mistralai/Devstral-Small-2-24B-Instruct-2512",
        "local-hf:mistralai/Mistral-Small-3.1-24B-Base-2503",
        "local-hf:Qwen/Qwen2.5-7B-Instruct",
        "local-hf:Qwen/Qwen3-4B-Instruct-2507",
        "ollama:qwen2.5:14b",
    ),
}

CURRENT_TEACHER_CANDIDATES = tuple(
    TEACHER_CANDIDATE_CATALOG[key] for key in TEACHER_CANDIDATE_ORDERS["quality"]
)

KNOWN_GPU_VRAM_MB = {
    "4090": 24564,
    "3090": 24576,
    "5090": 32768,
    "P2000": 5120,
}

configure_hf_env()


def _hf_cache_roots() -> list[Path]:
    return hf_cache_roots()


def hf_model_cached(model_id: str) -> bool:
    suffix = f"models--{model_id.replace('/', '--')}"
    for root in _hf_cache_roots():
        model_root = root / suffix
        snapshots_dir = model_root / "snapshots"
        if not snapshots_dir.exists():
            continue
        for snapshot in snapshots_dir.iterdir():
            if not snapshot.is_dir():
                continue
            if not (snapshot / "config.json").exists():
                continue
            if any(
                path.is_file() or path.is_symlink()
                for path in snapshot.glob("*.safetensors")
                if not path.name.endswith(".index.json")
            ):
                return True
    return False


def parse_param_b(model_name: str | None) -> float | None:
    if not model_name:
        return None
    match = _PARAM_RE.search(model_name)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def normalize_model_name(model_name: str | None) -> str:
    return (model_name or "").strip().lower()


def resolve_teacher_objective(objective: str | None) -> str:
    resolved = (objective or "balanced").strip().lower()
    if resolved not in TEACHER_OBJECTIVES:
        supported = ", ".join(TEACHER_OBJECTIVES)
        raise SystemExit(
            f"Unsupported teacher objective {objective!r}. Use one of: {supported}"
        )
    return resolved


def normalize_domains(domains: list[str] | None) -> list[str]:
    return [
        str(domain).strip().lower() for domain in (domains or []) if str(domain).strip()
    ]


def domains_prefer_devstral(domains: list[str] | None) -> bool:
    normalized = normalize_domains(domains)
    if not normalized:
        return False
    code_hits = sum(1 for domain in normalized if domain in CODE_HEAVY_DOMAINS)
    return code_hits * 2 >= len(normalized)


def infer_known_vram_mb(gpu_name: str | None) -> int:
    if not gpu_name:
        return 0
    upper = gpu_name.upper()
    for needle, total_vram_mb in KNOWN_GPU_VRAM_MB.items():
        if needle in upper:
            return total_vram_mb
    return 0


def detect_machine_profile(*, requested_device: str = "auto") -> dict:
    cpu_count = os.cpu_count() or 1
    cuda_available = False
    bf16 = False
    gpu_present = False
    gpu_name = None
    driver_version = None
    gpu_count = 0
    total_vram_mb = 0

    if torch is not None:
        try:
            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                gpu_count = int(torch.cuda.device_count())
                gpu_name = torch.cuda.get_device_name(0)
                total_vram_mb = int(
                    torch.cuda.get_device_properties(0).total_memory / 1024**2
                )
                bf16 = bool(torch.cuda.is_bf16_supported())
                gpu_present = gpu_count > 0
        except Exception:
            cuda_available = False

    if not gpu_present:
        info_root = Path("/proc/driver/nvidia/gpus")
        if info_root.exists():
            info_files = sorted(info_root.glob("*/information"))
            if info_files:
                gpu_count = len(info_files)
                gpu_present = gpu_count > 0
                try:
                    info_text = info_files[0].read_text(encoding="utf-8")
                    for line in info_text.splitlines():
                        if line.startswith("Model:"):
                            gpu_name = line.split(":", 1)[1].strip()
                            break
                except Exception:
                    pass
                if not total_vram_mb:
                    total_vram_mb = infer_known_vram_mb(gpu_name)
        version_path = Path("/proc/driver/nvidia/version")
        if version_path.exists() and driver_version is None:
            try:
                version_text = version_path.read_text(encoding="utf-8")
                match = re.search(r"NVRM version:\\s+NVIDIA\\s+(\\S+)", version_text)
                if match is not None:
                    driver_version = match.group(1)
            except Exception:
                pass

    if not gpu_present:
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                first = completed.stdout.strip().splitlines()[0]
                parts = [item.strip() for item in first.split(",")]
                if len(parts) >= 3:
                    gpu_name = gpu_name or parts[0]
                    try:
                        total_vram_mb = total_vram_mb or int(parts[1].split()[0])
                    except ValueError:
                        pass
                    driver_version = driver_version or parts[2]
                gpu_count = gpu_count or len(completed.stdout.strip().splitlines())
                gpu_present = gpu_count > 0
        except Exception:
            pass

    if gpu_present and total_vram_mb >= 22000:
        hardware_class = "gpu_24gb_plus"
    elif gpu_present and total_vram_mb >= 14000:
        hardware_class = "gpu_mid"
    elif gpu_present and total_vram_mb >= 6000:
        hardware_class = "gpu_small"
    elif gpu_present:
        hardware_class = "gpu_tiny"
    else:
        hardware_class = "cpu_only"

    return {
        "requested_device": requested_device,
        "cuda_available": cuda_available,
        "gpu_present": gpu_present,
        "gpu_count": gpu_count,
        "gpu_name": gpu_name,
        "driver_version": driver_version,
        "total_vram_mb": total_vram_mb,
        "bf16": bf16,
        "cpu_count": cpu_count,
        "hardware_class": hardware_class,
    }


def resolve_requested_device(requested_device: str, machine_profile: dict) -> str:
    requested = (requested_device or "auto").strip().lower()
    if requested == "cpu":
        return "cpu"
    if requested == "gpu":
        return "gpu"
    if gpu_runtime_available(machine_profile):
        return "gpu"
    return "cpu"


def gpu_runtime_available(machine_profile: dict) -> bool:
    return bool(
        machine_profile.get("cuda_available") or machine_profile.get("gpu_present")
    )


def resolve_default_student_model(
    *, machine_profile: dict, fallback_model: str, requested_device: str
) -> tuple[str, str]:
    if requested_device != "gpu" or not gpu_runtime_available(machine_profile):
        return fallback_model, "cpu-oriented fallback student"

    total_vram_mb = int(machine_profile.get("total_vram_mb") or 0)
    for candidate in CURRENT_STUDENT_CANDIDATES:
        if total_vram_mb >= int(candidate["min_vram_mb"]):
            return candidate["model"], str(candidate["reason"])
    return (
        fallback_model,
        "fallback student because no newer candidate fits the detected VRAM",
    )


def infer_teacher_provider_from_model(model_name: str | None) -> str:
    if model_name and "/" in model_name:
        return "local-hf"
    return "ollama"


def default_teacher_model(provider: str) -> str:
    if provider == "local-hf":
        return CURRENT_TEACHER_CANDIDATES[0]["model"]
    return "qwen2.5:14b"


def probe_ollama(api_url: str | None = None) -> tuple[bool, str]:
    target = (api_url or DEFAULT_OLLAMA_API_URL).rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(target, timeout=5) as response:
            response.read(64)
        return True, f"reachable: {target}"
    except urllib.error.URLError as exc:
        return False, str(exc)


def resolve_local_hf_teacher_runtime(
    model_name: str, machine_profile: dict
) -> tuple[str, bool, str]:
    if not gpu_runtime_available(machine_profile):
        return (
            "cpu",
            False,
            "CUDA runtime unavailable; keep the local-hf teacher on CPU",
        )

    normalized = normalize_model_name(model_name)
    if normalized in FULL_GPU_LOCAL_HF_TEACHERS:
        return (
            "cuda:0",
            True,
            "validated dense local-hf teacher for true single-GPU compute on this machine",
        )
    if normalized in OFFLOAD_LOCAL_HF_TEACHERS:
        return (
            "auto",
            True,
            "heavy local-hf teacher kept in auto/offload mode on a single 24 GB GPU",
        )

    params_b = parse_param_b(model_name)
    if params_b is not None and params_b <= 8.0:
        return (
            "cuda:0",
            True,
            "dense local-hf teacher small enough to default to cuda:0",
        )
    return (
        "auto",
        True,
        "unknown or large local-hf teacher kept on device_map=auto by default",
    )


def build_teacher_plan(
    *,
    provider: str,
    model: str,
    mode: str,
    machine_profile: dict,
    reason: str,
    candidates_considered: list[dict],
    ollama_api_url: str | None = None,
    local_hf_device: str | None = None,
    gpu_active: bool | None = None,
    objective: str = "balanced",
) -> dict:
    runtime_reason = None
    if provider == "local-hf":
        (
            default_local_hf_device,
            default_gpu_active,
            runtime_reason,
        ) = resolve_local_hf_teacher_runtime(model, machine_profile)
        if local_hf_device is None:
            local_hf_device = default_local_hf_device
        if gpu_active is None:
            gpu_active = default_gpu_active
    else:
        local_hf_device = None
        gpu_active = False
    resolved_reason = reason
    if runtime_reason and runtime_reason not in reason:
        resolved_reason = f"{reason}; {runtime_reason}"
    return {
        "mode": mode,
        "objective": resolve_teacher_objective(objective),
        "provider": provider,
        "model": model,
        "local_hf_device": local_hf_device,
        "gpu_active": gpu_active,
        "reason": resolved_reason,
        "candidates_considered": candidates_considered,
        "ollama_api_url": (ollama_api_url or DEFAULT_OLLAMA_API_URL).rstrip("/"),
    }


def teacher_candidate_order(
    *,
    objective: str,
    machine_profile: dict,
    domains: list[str] | None,
) -> tuple[str, ...]:
    resolved_objective = resolve_teacher_objective(objective)
    base_order = list(TEACHER_CANDIDATE_ORDERS[resolved_objective])
    if machine_profile.get(
        "hardware_class"
    ) == "gpu_24gb_plus" and domains_prefer_devstral(domains):
        devstral_key = "local-hf:mistralai/Devstral-Small-2-24B-Instruct-2512"
        if devstral_key in base_order:
            base_order.remove(devstral_key)
            if resolved_objective == "quality":
                insert_at = 0
            elif resolved_objective == "balanced":
                insert_at = 1
            else:
                insert_at = 2
            base_order.insert(insert_at, devstral_key)
    return tuple(base_order)


def resolve_teacher_selection(
    *,
    machine_profile: dict,
    explicit_provider: str | None,
    explicit_model: str | None,
    ollama_api_url: str | None = None,
    domains: list[str] | None = None,
    objective: str = "balanced",
) -> dict:
    resolved_objective = resolve_teacher_objective(objective)
    considered: list[dict] = []
    constrained_provider = (
        explicit_provider.strip()
        if explicit_provider and explicit_provider.strip()
        else None
    )
    constrained_model = (
        explicit_model.strip() if explicit_model and explicit_model.strip() else None
    )
    if constrained_model is not None:
        provider = constrained_provider or infer_teacher_provider_from_model(
            constrained_model
        )
        model = constrained_model
        reason = f"manual override from CLI (teacher objective={resolved_objective})"
        return build_teacher_plan(
            provider=provider,
            model=model,
            mode="manual",
            machine_profile=machine_profile,
            reason=reason,
            candidates_considered=considered,
            ollama_api_url=ollama_api_url,
            objective=resolved_objective,
        )

    total_vram_mb = int(machine_profile.get("total_vram_mb") or 0)
    for candidate_key in teacher_candidate_order(
        objective=resolved_objective,
        machine_profile=machine_profile,
        domains=domains,
    ):
        candidate = TEACHER_CANDIDATE_CATALOG[candidate_key]
        if (
            constrained_provider is not None
            and candidate["provider"] != constrained_provider
        ):
            continue
        record = {
            "provider": candidate["provider"],
            "model": candidate["model"],
            "source": candidate["source"],
        }
        if candidate["provider"] == "local-hf":
            if not candidate.get("auto_enabled", True):
                record["available"] = False
                record["reason"] = "manual-only local teacher candidate"
                considered.append(record)
                continue
            if not gpu_runtime_available(machine_profile):
                record["available"] = False
                record["reason"] = "CUDA runtime unavailable for local-hf GPU teachers"
                considered.append(record)
                continue
            if total_vram_mb < int(candidate["min_vram_mb"]):
                record["available"] = False
                record["reason"] = (
                    f"requires >= {candidate['min_vram_mb']} MB VRAM, detected {total_vram_mb} MB"
                )
                considered.append(record)
                continue
            cached = hf_model_cached(candidate["model"])
            record["cached"] = cached
            if not cached:
                record["available"] = False
                record["reason"] = "model not cached locally"
                considered.append(record)
                continue
            record["available"] = True
            record["reason"] = candidate["reason"]
            considered.append(record)
            return build_teacher_plan(
                provider=candidate["provider"],
                model=candidate["model"],
                mode="auto",
                machine_profile=machine_profile,
                reason=candidate["reason"],
                candidates_considered=considered,
                ollama_api_url=ollama_api_url,
                local_hf_device=candidate.get("local_hf_device"),
                gpu_active=candidate.get("gpu_active"),
                objective=resolved_objective,
            )

        reachable, reach_reason = probe_ollama(ollama_api_url)
        record["available"] = reachable
        record["reason"] = reach_reason if not reachable else candidate["reason"]
        considered.append(record)
        if reachable:
            return build_teacher_plan(
                provider=candidate["provider"],
                model=candidate["model"],
                mode="auto",
                machine_profile=machine_profile,
                reason=candidate["reason"],
                candidates_considered=considered,
                ollama_api_url=ollama_api_url,
                objective=resolved_objective,
            )

    return build_teacher_plan(
        provider=constrained_provider or "ollama",
        model=default_teacher_model(constrained_provider or "ollama"),
        mode="auto",
        machine_profile=machine_profile,
        reason=(
            "fallback teacher because no "
            f"{resolved_objective} candidate was available"
            + (
                f" for provider {constrained_provider}"
                if constrained_provider is not None
                else ""
            )
        ),
        candidates_considered=considered,
        ollama_api_url=ollama_api_url,
        objective=resolved_objective,
    )


def resolve_autotune_plan(
    *,
    machine_profile: dict,
    student_model: str,
    requested_device: str,
    teacher_selection: dict,
    requested_gpu_slots: int | None,
    requested_seq_len: int | None,
    requested_student_max_samples: int | None,
) -> dict:
    parameter_scale_b = parse_param_b(student_model) or 1.5
    total_vram_mb = int(machine_profile.get("total_vram_mb") or 0)
    gpu_device = requested_device == "gpu" and bool(machine_profile.get("gpu_present"))

    if requested_gpu_slots is not None:
        resolved_gpu_slots = int(requested_gpu_slots)
        gpu_slots_source = "manual"
    elif not gpu_device:
        resolved_gpu_slots = 1
        gpu_slots_source = "auto"
    elif teacher_selection.get("gpu_active"):
        resolved_gpu_slots = 1
        gpu_slots_source = "auto"
    elif total_vram_mb >= 22000 and parameter_scale_b <= 4.5:
        resolved_gpu_slots = 2
        gpu_slots_source = "auto"
    else:
        resolved_gpu_slots = 1
        gpu_slots_source = "auto"

    if requested_seq_len is not None:
        resolved_seq_len = int(requested_seq_len)
        seq_len_source = "manual"
    else:
        if parameter_scale_b <= 2.1:
            resolved_seq_len = 1024 if total_vram_mb >= 8000 else 768
        elif parameter_scale_b <= 4.5:
            resolved_seq_len = 1024 if total_vram_mb >= 22000 else 768
        elif parameter_scale_b <= 9.5:
            resolved_seq_len = 768 if total_vram_mb >= 22000 else 512
        else:
            resolved_seq_len = 512
        seq_len_source = "auto"

    if requested_student_max_samples is not None:
        resolved_student_max_samples = int(requested_student_max_samples)
        student_samples_source = "manual"
    else:
        if not gpu_device:
            resolved_student_max_samples = 64
        elif total_vram_mb >= 22000:
            resolved_student_max_samples = 750 if parameter_scale_b <= 4.5 else 384
        elif total_vram_mb >= 12000:
            resolved_student_max_samples = 256 if parameter_scale_b <= 4.5 else 128
        else:
            resolved_student_max_samples = 128 if parameter_scale_b <= 2.1 else 64
        student_samples_source = "auto"

    if teacher_selection.get("gpu_active"):
        reason = (
            "teacher is scheduled on the local GPU; keep a balanced student profile"
        )
    elif total_vram_mb >= 22000:
        reason = "24 GB class GPU detected; use the balanced high-VRAM student profile"
    elif total_vram_mb >= 12000:
        reason = "mid-range GPU detected; use the balanced mid-VRAM student profile"
    else:
        reason = "constrained hardware detected; use the conservative student profile"

    return {
        "objective": "balanced",
        "reason": reason,
        "parameter_scale_b": parameter_scale_b,
        "gpu_slots_source": gpu_slots_source,
        "seq_len_source": seq_len_source,
        "student_max_samples_source": student_samples_source,
        "resolved_gpu_slots": resolved_gpu_slots,
        "resolved_seq_len": resolved_seq_len,
        "resolved_student_max_samples": resolved_student_max_samples,
    }
