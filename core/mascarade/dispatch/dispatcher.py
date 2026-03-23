"""Dispatcher with capability matching for multi-machine job dispatch."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mascarade.dispatch.models import Job, JobRequirements

logger = logging.getLogger("mascarade.dispatch.dispatcher")

DEFAULT_MACHINE_PROFILES_PATH = Path(
    os.getenv("MACHINE_PROFILES_PATH", "").strip()
    or "/mascarade/docs/MACHINE_PROFILES.json"
)


@dataclass(slots=True)
class MachineProfile:
    """Machine profile with capabilities and metadata."""

    machine_id: str
    aliases: set[str]
    capabilities: set[str]

    def matches_requirements(self, requirements: JobRequirements) -> bool:
        """Check if machine matches job requirements.

        Args:
            requirements: Job requirements to match.

        Returns:
            True if machine satisfies all requirements.
        """
        # Check capability requirements
        if requirements.capabilities:
            if not all(cap in self.capabilities for cap in requirements.capabilities):
                return False

        # Check GPU requirement
        if requirements.gpu_required:
            gpu_capabilities = {"gpu", "cuda", "nvidia", "rtx"}
            if not any(cap in self.capabilities for cap in gpu_capabilities):
                return False

        # Check ANE requirement
        if requirements.ane_required:
            ane_capabilities = {"ane", "apple-neural-engine", "apple-silicon"}
            if not any(cap in self.capabilities for cap in ane_capabilities):
                return False

        return True

    def score_for_job(self, job: Job) -> float:
        """Calculate suitability score for a job.

        Higher score means better match. Returns 0 if machine doesn't match.

        Args:
            job: Job to score.

        Returns:
            Score between 0 and 100.
        """
        if not self.matches_requirements(job.requirements):
            return 0.0

        score = 50.0  # Base score for matching

        # Bonus for preferred machine
        if job.requirements.preferred_machine:
            if (
                job.requirements.preferred_machine == self.machine_id
                or job.requirements.preferred_machine in self.aliases
            ):
                score += 30.0

        # Bonus for GPU capability when GPU required
        if job.requirements.gpu_required:
            gpu_caps = {"gpu", "cuda", "nvidia", "rtx"}
            matching_gpu_caps = gpu_caps.intersection(self.capabilities)
            if matching_gpu_caps:
                score += 15.0

        # Bonus for ANE capability when ANE required
        if job.requirements.ane_required:
            ane_caps = {"ane", "apple-neural-engine", "apple-silicon"}
            matching_ane_caps = ane_caps.intersection(self.capabilities)
            if matching_ane_caps:
                score += 15.0

        # Small bonus for exact capability match (no extras)
        required_caps = set(job.requirements.capabilities)
        if required_caps and required_caps == self.capabilities:
            score += 5.0

        return min(score, 100.0)


@dataclass(slots=True)
class MachineCandidate:
    """Candidate machine for job assignment."""

    machine_id: str
    profile: MachineProfile
    score: float
    reason: str


class DispatchError(RuntimeError):
    """Base error for dispatch operations."""


class NoMachineAvailableError(DispatchError):
    """Raised when no suitable machine is available for a job."""


class Dispatcher:
    """Dispatcher that matches jobs to machines based on capabilities.

    Loads machine profiles and provides capability matching logic to
    select the best machine for a given job.
    """

    def __init__(
        self,
        *,
        profiles_path: Path | None = None,
        machine_profiles: dict[str, MachineProfile] | None = None,
    ) -> None:
        """Initialize dispatcher.

        Args:
            profiles_path: Path to machine profiles JSON. If None, uses default.
            machine_profiles: Pre-loaded machine profiles. If provided, profiles_path is ignored.
        """
        self._profiles_path = profiles_path or DEFAULT_MACHINE_PROFILES_PATH
        if machine_profiles is not None:
            self._machine_profiles = machine_profiles
        else:
            self._machine_profiles = self._load_machine_profiles()

    def _load_machine_profiles(self) -> dict[str, MachineProfile]:
        """Load machine profiles from JSON file.

        Returns:
            Dictionary of machine_id to MachineProfile.
        """
        profiles: dict[str, MachineProfile] = {}

        if not self._profiles_path.exists():
            logger.warning(
                "Machine profiles file not found: %s (dispatcher will run with no machines)",
                self._profiles_path,
            )
            return profiles

        try:
            data = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            machines = data.get("machines", {})

            for machine_id, machine_data in machines.items():
                aliases_raw = machine_data.get("aliases", [])
                aliases = {
                    str(item).strip() for item in aliases_raw if str(item).strip()
                }
                aliases.add(machine_id)

                capabilities_raw = machine_data.get("capabilities", [])
                capabilities = {
                    str(item).strip().lower()
                    for item in capabilities_raw
                    if str(item).strip()
                }

                profile = MachineProfile(
                    machine_id=machine_id,
                    aliases=aliases,
                    capabilities=capabilities,
                )
                profiles[machine_id] = profile

            logger.info(
                "Loaded %d machine profiles from %s",
                len(profiles),
                self._profiles_path,
            )

        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(
                "Failed to load machine profiles from %s: %s",
                self._profiles_path,
                exc,
            )
            return {}

        return profiles

    def reload_profiles(self) -> None:
        """Reload machine profiles from disk.

        Useful for picking up profile changes without restarting the service.
        """
        self._machine_profiles = self._load_machine_profiles()

    def get_machine_profile(self, machine_id: str) -> MachineProfile | None:
        """Get machine profile by ID or alias.

        Args:
            machine_id: Machine ID or alias.

        Returns:
            MachineProfile if found, None otherwise.
        """
        # Direct lookup by machine_id
        if machine_id in self._machine_profiles:
            return self._machine_profiles[machine_id]

        # Lookup by alias
        for profile in self._machine_profiles.values():
            if machine_id in profile.aliases:
                return profile

        return None

    def list_machines(self) -> list[MachineProfile]:
        """List all registered machine profiles.

        Returns:
            List of MachineProfile objects.
        """
        return list(self._machine_profiles.values())

    def find_candidates(
        self,
        job: Job,
        *,
        available_machines: list[str] | None = None,
    ) -> list[MachineCandidate]:
        """Find candidate machines for a job.

        Args:
            job: Job to find candidates for.
            available_machines: List of machine IDs to consider. If None, considers all.

        Returns:
            List of candidates, sorted by score (best first).
        """
        candidates: list[MachineCandidate] = []

        # Determine which machines to consider
        machine_pool = self._machine_profiles
        if available_machines is not None:
            machine_pool = {
                mid: profile
                for mid, profile in self._machine_profiles.items()
                if mid in available_machines
            }

        # Filter out excluded machines
        excluded = set(job.requirements.exclude_machines)

        for machine_id, profile in machine_pool.items():
            # Skip excluded machines
            if machine_id in excluded or any(
                alias in excluded for alias in profile.aliases
            ):
                continue

            # Calculate score
            score = profile.score_for_job(job)
            if score <= 0:
                continue

            # Determine reason
            reason_parts = []
            if job.requirements.preferred_machine == machine_id:
                reason_parts.append("preferred")
            if profile.matches_requirements(job.requirements):
                reason_parts.append("capabilities match")

            reason = ", ".join(reason_parts) if reason_parts else "match"

            candidates.append(
                MachineCandidate(
                    machine_id=machine_id,
                    profile=profile,
                    score=score,
                    reason=reason,
                )
            )

        # Sort by score (highest first) then by machine_id for stability
        candidates.sort(key=lambda c: (-c.score, c.machine_id))

        return candidates

    def select_machine(
        self,
        job: Job,
        *,
        available_machines: list[str] | None = None,
    ) -> str:
        """Select the best machine for a job.

        Args:
            job: Job to select machine for.
            available_machines: List of machine IDs to consider. If None, considers all.

        Returns:
            Machine ID of selected machine.

        Raises:
            NoMachineAvailableError: If no suitable machine is found.
        """
        candidates = self.find_candidates(job, available_machines=available_machines)

        if not candidates:
            raise NoMachineAvailableError(
                f"No suitable machine found for job {job.job_id} "
                f"(requirements: {job.requirements.to_dict()})"
            )

        selected = candidates[0]
        logger.info(
            "Selected machine %s for job %s (score=%.1f, reason=%s)",
            selected.machine_id,
            job.job_id,
            selected.score,
            selected.reason,
        )

        return selected.machine_id

    def machine_count(self) -> int:
        """Return the number of registered machines.

        Returns:
            Number of machines.
        """
        return len(self._machine_profiles)

    def to_dict(self) -> dict[str, Any]:
        """Serialize dispatcher state to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "profiles_path": str(self._profiles_path),
            "machine_count": self.machine_count(),
            "machines": [
                {
                    "machine_id": profile.machine_id,
                    "aliases": list(profile.aliases),
                    "capabilities": list(profile.capabilities),
                }
                for profile in self._machine_profiles.values()
            ],
        }
