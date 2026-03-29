"""Tests for mascarade.machine_profile — hardware detection and provider affinity."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mascarade.machine_profile import (
    _OVERRIDE_PROFILES,
    ChipFamily,
    MachineProfile,
    _detect_apple_silicon,
    _detect_metal,
    _detect_nvidia_gpu,
    detect_machine_profile,
)

# ---------------------------------------------------------------------------
# ChipFamily enum
# ---------------------------------------------------------------------------


class TestChipFamily:
    def test_values(self):
        assert ChipFamily.APPLE_SILICON == "apple_silicon"
        assert ChipFamily.NVIDIA_GPU == "nvidia_gpu"
        assert ChipFamily.CPU_ONLY == "cpu_only"

    def test_from_string(self):
        assert ChipFamily("apple_silicon") is ChipFamily.APPLE_SILICON
        assert ChipFamily("nvidia_gpu") is ChipFamily.NVIDIA_GPU
        assert ChipFamily("cpu_only") is ChipFamily.CPU_ONLY


# ---------------------------------------------------------------------------
# MachineProfile dataclass
# ---------------------------------------------------------------------------


class TestMachineProfile:
    def test_frozen(self):
        p = MachineProfile(chip=ChipFamily.CPU_ONLY)
        with pytest.raises(AttributeError):
            p.chip = ChipFamily.NVIDIA_GPU  # type: ignore[misc]

    def test_defaults(self):
        p = MachineProfile(chip=ChipFamily.CPU_ONLY)
        assert p.gpu_model == ""
        assert p.gpu_vram_gb == 0.0
        assert p.has_ane is False
        assert p.has_metal is False
        assert p.cpu_cores == 0
        assert p.ram_gb == 0.0


# ---------------------------------------------------------------------------
# preferred_providers for each chip family
# ---------------------------------------------------------------------------


class TestPreferredProviders:
    def test_apple_silicon_prefers_mlx(self):
        p = MachineProfile(chip=ChipFamily.APPLE_SILICON, has_ane=True, has_metal=True)
        prefs = p.preferred_providers
        assert prefs[0] == "mlx_lm"
        assert "claude" in prefs
        assert "openai" in prefs
        # Apple preferred providers come before cloud
        apple_idx = prefs.index("mlx_lm")
        cloud_idx = prefs.index("claude")
        assert apple_idx < cloud_idx

    def test_nvidia_prefers_ollama(self):
        p = MachineProfile(chip=ChipFamily.NVIDIA_GPU, gpu_model="RTX 4090", gpu_vram_gb=24.0)
        prefs = p.preferred_providers
        assert prefs[0] == "ollama"
        assert "claude" in prefs

    def test_cpu_only_cloud_first(self):
        p = MachineProfile(chip=ChipFamily.CPU_ONLY)
        prefs = p.preferred_providers
        assert prefs == MachineProfile.CLOUD_PROVIDERS

    def test_cloud_providers_always_present(self):
        for chip in ChipFamily:
            p = MachineProfile(chip=chip)
            for cloud in ("claude", "openai", "mistral"):
                assert cloud in p.preferred_providers


# ---------------------------------------------------------------------------
# Override profiles
# ---------------------------------------------------------------------------


class TestOverrideProfiles:
    def test_apple_m4_override(self):
        p = _OVERRIDE_PROFILES["apple_m4"]
        assert p.chip == ChipFamily.APPLE_SILICON
        assert p.gpu_model == "Apple M4"
        assert p.has_ane is True
        assert p.has_metal is True
        assert p.cpu_cores == 10
        assert p.ram_gb == 24.0

    def test_nvidia_4090_override(self):
        p = _OVERRIDE_PROFILES["nvidia_4090"]
        assert p.chip == ChipFamily.NVIDIA_GPU
        assert p.gpu_model == "NVIDIA GeForce RTX 4090"
        assert p.gpu_vram_gb == 24.0

    def test_cpu_only_override(self):
        p = _OVERRIDE_PROFILES["cpu_only"]
        assert p.chip == ChipFamily.CPU_ONLY
        assert p.gpu_model == ""
        assert p.has_ane is False

    def test_all_overrides_have_valid_chip(self):
        for key, profile in _OVERRIDE_PROFILES.items():
            assert isinstance(profile.chip, ChipFamily), f"{key} has invalid chip"


# ---------------------------------------------------------------------------
# detect_machine_profile (with mocks)
# ---------------------------------------------------------------------------


class TestDetectMachineProfile:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Clear lru_cache between tests."""
        detect_machine_profile.cache_clear()
        yield
        detect_machine_profile.cache_clear()

    def test_override_apple_m4(self):
        p = detect_machine_profile(override="apple_m4")
        assert p.chip == ChipFamily.APPLE_SILICON
        assert p.gpu_model == "Apple M4"

    def test_override_case_insensitive(self):
        p = detect_machine_profile(override="  NVIDIA_4090  ")
        assert p.chip == ChipFamily.NVIDIA_GPU

    def test_override_unknown_falls_back(self):
        """Unknown override triggers auto-detect."""
        with (
            patch("mascarade.machine_profile._detect_apple_silicon", return_value=False),
            patch("mascarade.machine_profile._detect_nvidia_gpu", return_value=("", 0.0)),
            patch("mascarade.machine_profile._cpu_cores", return_value=4),
            patch("mascarade.machine_profile._ram_gb", return_value=8.0),
        ):
            p = detect_machine_profile(override="unknown_chip_xyz")
        assert p.chip == ChipFamily.CPU_ONLY

    def test_detect_apple_silicon(self):
        with (
            patch("mascarade.machine_profile._detect_apple_silicon", return_value=True),
            patch("mascarade.machine_profile._detect_apple_chip_name", return_value="Apple M3 Pro"),
            patch("mascarade.machine_profile._cpu_cores", return_value=12),
            patch("mascarade.machine_profile._ram_gb", return_value=36.0),
        ):
            p = detect_machine_profile(override="")
        assert p.chip == ChipFamily.APPLE_SILICON
        assert p.gpu_model == "Apple M3 Pro"
        assert p.has_ane is True
        assert p.has_metal is True

    def test_detect_nvidia(self):
        with (
            patch("mascarade.machine_profile._detect_apple_silicon", return_value=False),
            patch(
                "mascarade.machine_profile._detect_nvidia_gpu", return_value=("NVIDIA A100", 80.0)
            ),
            patch("mascarade.machine_profile._cpu_cores", return_value=64),
            patch("mascarade.machine_profile._ram_gb", return_value=256.0),
        ):
            p = detect_machine_profile(override="")
        assert p.chip == ChipFamily.NVIDIA_GPU
        assert p.gpu_model == "NVIDIA A100"
        assert p.gpu_vram_gb == 80.0

    def test_detect_cpu_only(self):
        with (
            patch("mascarade.machine_profile._detect_apple_silicon", return_value=False),
            patch("mascarade.machine_profile._detect_nvidia_gpu", return_value=("", 0.0)),
            patch("mascarade.machine_profile._cpu_cores", return_value=8),
            patch("mascarade.machine_profile._ram_gb", return_value=16.0),
        ):
            p = detect_machine_profile(override="")
        assert p.chip == ChipFamily.CPU_ONLY
        assert p.cpu_cores == 8
        assert p.ram_gb == 16.0


# ---------------------------------------------------------------------------
# Detection helpers with mocked platform
# ---------------------------------------------------------------------------


class TestDetectionHelpers:
    def test_apple_silicon_on_darwin_arm64(self):
        with (
            patch("mascarade.machine_profile.platform.system", return_value="Darwin"),
            patch("mascarade.machine_profile.platform.machine", return_value="arm64"),
        ):
            assert _detect_apple_silicon() is True

    def test_apple_silicon_on_linux(self):
        with (
            patch("mascarade.machine_profile.platform.system", return_value="Linux"),
            patch("mascarade.machine_profile.platform.machine", return_value="x86_64"),
        ):
            assert _detect_apple_silicon() is False

    def test_apple_silicon_on_darwin_x86(self):
        with (
            patch("mascarade.machine_profile.platform.system", return_value="Darwin"),
            patch("mascarade.machine_profile.platform.machine", return_value="x86_64"),
        ):
            assert _detect_apple_silicon() is False

    def test_metal_on_arm64_mac(self):
        with (
            patch("mascarade.machine_profile.platform.system", return_value="Darwin"),
            patch("mascarade.machine_profile.platform.machine", return_value="arm64"),
        ):
            assert _detect_metal() is True

    def test_metal_on_linux(self):
        with patch("mascarade.machine_profile.platform.system", return_value="Linux"):
            assert _detect_metal() is False

    def test_nvidia_not_found(self):
        with patch(
            "mascarade.machine_profile.subprocess.check_output",
            side_effect=FileNotFoundError,
        ):
            model, vram = _detect_nvidia_gpu()
            assert model == ""
            assert vram == 0.0


# ---------------------------------------------------------------------------
# CPU forced-profile validation (Phase D)
# ---------------------------------------------------------------------------


class TestCpuForcedProfile:
    """Verify the CPU-only path is enforced when explicitly requested."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        detect_machine_profile.cache_clear()
        yield
        detect_machine_profile.cache_clear()

    def test_cpu_forced_overrides_gpu_env(self):
        """override='cpu_only' must return CPU profile even when GPU is detected."""
        with (
            patch("mascarade.machine_profile._detect_apple_silicon", return_value=True),
            patch(
                "mascarade.machine_profile._detect_nvidia_gpu",
                return_value=("RTX 4090", 24.0),
            ),
        ):
            p = detect_machine_profile(override="cpu_only")
        assert p.chip == ChipFamily.CPU_ONLY
        assert p.has_ane is False
        assert p.has_metal is False
        assert p.gpu_vram_gb == 0.0

    def test_cpu_only_preferred_providers_are_cloud_only(self):
        """CPU-only profile must not expose any local GPU providers."""
        p = MachineProfile(chip=ChipFamily.CPU_ONLY)
        prefs = p.preferred_providers
        assert prefs == MachineProfile.CLOUD_PROVIDERS
        for local_provider in ("ollama", "mlx_lm", "mlx", "vllm", "apple_fm"):
            assert local_provider not in prefs, (
                f"Local provider {local_provider!r} must not appear in CPU-only preferred list"
            )

    def test_cpu_only_override_profile_is_cloud_only(self):
        """The 'cpu_only' preset in _OVERRIDE_PROFILES must expose cloud-only providers."""
        p = _OVERRIDE_PROFILES["cpu_only"]
        assert p.chip == ChipFamily.CPU_ONLY
        assert p.preferred_providers == MachineProfile.CLOUD_PROVIDERS
