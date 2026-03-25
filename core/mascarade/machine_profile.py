"""Machine profile detection — hardware-aware routing support.

Detects local hardware (Apple Silicon, NVIDIA GPU, CPU-only) and exposes a
cached ``MachineProfile`` that the router can use to prefer the right providers.
"""

from __future__ import annotations

import functools
import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger("mascarade.machine_profile")


class ChipFamily(StrEnum):
    APPLE_SILICON = "apple_silicon"
    NVIDIA_GPU = "nvidia_gpu"
    CPU_ONLY = "cpu_only"


@dataclass(frozen=True)
class MachineProfile:
    """Immutable snapshot of the local hardware."""

    chip: ChipFamily
    gpu_model: str = ""
    gpu_vram_gb: float = 0.0
    has_ane: bool = False  # Apple Neural Engine
    has_metal: bool = False
    cpu_cores: int = 0
    ram_gb: float = 0.0

    # ── Provider affinity helpers ────────────────────────────────────

    #: Providers that benefit from Apple Silicon (MLX, CoreML, Apple FM)
    APPLE_PREFERRED: tuple[str, ...] = (
        "mlx_lm",
        "mlx",
        "apple-coreml",
        "apple_fm",
    )

    #: Providers that need an NVIDIA GPU (vLLM, Ollama w/ CUDA, exo)
    NVIDIA_PREFERRED: tuple[str, ...] = (
        "ollama",
        "exo",
        "llama_cpp",
    )

    #: Cloud providers — always available regardless of hardware
    CLOUD_PROVIDERS: tuple[str, ...] = (
        "claude",
        "openai",
        "mistral",
        "google",
        "bedrock",
        "huggingface",
        "litellm",
        "codestral",
        "github-copilot",
    )

    @property
    def preferred_providers(self) -> tuple[str, ...]:
        """Return provider names this machine should prefer, in priority order."""
        if self.chip == ChipFamily.APPLE_SILICON:
            return self.APPLE_PREFERRED + self.CLOUD_PROVIDERS
        if self.chip == ChipFamily.NVIDIA_GPU:
            return self.NVIDIA_PREFERRED + self.CLOUD_PROVIDERS
        # CPU-only: cloud first
        return self.CLOUD_PROVIDERS


# ── Detection helpers ────────────────────────────────────────────────


def _detect_apple_silicon() -> bool:
    """Return True if running on Apple Silicon (arm64 macOS)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _detect_apple_chip_name() -> str:
    """Best-effort chip name (e.g. 'Apple M2 Pro')."""
    if platform.system() != "Darwin":
        return ""
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            timeout=5,
        ).strip()
        return out
    except Exception:
        return "Apple Silicon (unknown)"


def _detect_nvidia_gpu() -> tuple[str, float]:
    """Return (gpu_model, vram_gb) if nvidia-smi is available."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        ).strip()
        if out:
            # Take first GPU line
            line = out.splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            name = parts[0] if parts else "NVIDIA GPU"
            vram_mb = float(parts[1]) if len(parts) > 1 else 0.0
            return name, round(vram_mb / 1024, 1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return "", 0.0


def _detect_metal() -> bool:
    """Check if Metal is likely available (macOS with Apple Silicon or AMD)."""
    if platform.system() != "Darwin":
        return False
    # On macOS arm64 Metal is always present
    if platform.machine() == "arm64":
        return True
    # On Intel Macs, check for Metal support via system_profiler (expensive)
    return False


def _detect_ane() -> bool:
    """Apple Neural Engine is present on all Apple Silicon Macs."""
    return _detect_apple_silicon()


def _cpu_cores() -> int:
    return os.cpu_count() or 1


def _ram_gb() -> float:
    """Total system RAM in GB."""
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"],
                text=True,
                timeout=5,
            ).strip()
            return round(int(out) / (1024**3), 1)
        except Exception:
            pass
    # Linux fallback
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
                    return round(kb / (1024**2), 1)
    except Exception:
        pass
    return 0.0


# ── Override parsing ─────────────────────────────────────────────────


_OVERRIDE_PROFILES: dict[str, MachineProfile] = {
    "apple_m1": MachineProfile(
        chip=ChipFamily.APPLE_SILICON,
        gpu_model="Apple M1",
        has_ane=True,
        has_metal=True,
        cpu_cores=8,
        ram_gb=16.0,
    ),
    "apple_m2": MachineProfile(
        chip=ChipFamily.APPLE_SILICON,
        gpu_model="Apple M2",
        has_ane=True,
        has_metal=True,
        cpu_cores=8,
        ram_gb=16.0,
    ),
    "apple_m3": MachineProfile(
        chip=ChipFamily.APPLE_SILICON,
        gpu_model="Apple M3",
        has_ane=True,
        has_metal=True,
        cpu_cores=8,
        ram_gb=18.0,
    ),
    "apple_m4": MachineProfile(
        chip=ChipFamily.APPLE_SILICON,
        gpu_model="Apple M4",
        has_ane=True,
        has_metal=True,
        cpu_cores=10,
        ram_gb=24.0,
    ),
    "nvidia_4090": MachineProfile(
        chip=ChipFamily.NVIDIA_GPU,
        gpu_model="NVIDIA GeForce RTX 4090",
        gpu_vram_gb=24.0,
        cpu_cores=16,
        ram_gb=64.0,
    ),
    "nvidia_a100": MachineProfile(
        chip=ChipFamily.NVIDIA_GPU,
        gpu_model="NVIDIA A100",
        gpu_vram_gb=80.0,
        cpu_cores=64,
        ram_gb=256.0,
    ),
    "cpu_only": MachineProfile(
        chip=ChipFamily.CPU_ONLY,
        cpu_cores=8,
        ram_gb=16.0,
    ),
}


# ── Public API ───────────────────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def detect_machine_profile(override: str = "") -> MachineProfile:
    """Detect (or override) the local machine profile.  Cached after first call."""
    if override:
        key = override.strip().lower()
        if key in _OVERRIDE_PROFILES:
            logger.info("Using machine profile override: %s", key)
            return _OVERRIDE_PROFILES[key]
        logger.warning("Unknown machine_profile_override '%s', falling back to auto-detect", key)

    # Auto-detect
    if _detect_apple_silicon():
        chip_name = _detect_apple_chip_name()
        profile = MachineProfile(
            chip=ChipFamily.APPLE_SILICON,
            gpu_model=chip_name,
            has_ane=True,
            has_metal=True,
            cpu_cores=_cpu_cores(),
            ram_gb=_ram_gb(),
        )
        logger.info("Detected Apple Silicon: %s (%s GB RAM)", chip_name, profile.ram_gb)
        return profile

    gpu_model, gpu_vram = _detect_nvidia_gpu()
    if gpu_model:
        profile = MachineProfile(
            chip=ChipFamily.NVIDIA_GPU,
            gpu_model=gpu_model,
            gpu_vram_gb=gpu_vram,
            cpu_cores=_cpu_cores(),
            ram_gb=_ram_gb(),
        )
        logger.info("Detected NVIDIA GPU: %s (%.1f GB VRAM)", gpu_model, gpu_vram)
        return profile

    profile = MachineProfile(
        chip=ChipFamily.CPU_ONLY,
        cpu_cores=_cpu_cores(),
        ram_gb=_ram_gb(),
    )
    logger.info("No accelerator detected — CPU-only profile")
    return profile
