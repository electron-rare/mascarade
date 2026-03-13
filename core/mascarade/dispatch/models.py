"""Data models for job dispatch across multi-machine fleet."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    """Job execution status."""

    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobRequirements:
    """Capability requirements for job dispatch."""

    capabilities: list[str] = field(default_factory=list)
    min_cpu_cores: int | None = None
    min_memory_gb: int | None = None
    gpu_required: bool = False
    ane_required: bool = False
    preferred_machine: str | None = None
    exclude_machines: list[str] = field(default_factory=list)

    def matches_capabilities(self, available: list[str]) -> bool:
        """Check if available capabilities satisfy requirements."""
        if not self.capabilities:
            return True
        return all(cap in available for cap in self.capabilities)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "capabilities": self.capabilities,
            "min_cpu_cores": self.min_cpu_cores,
            "min_memory_gb": self.min_memory_gb,
            "gpu_required": self.gpu_required,
            "ane_required": self.ane_required,
            "preferred_machine": self.preferred_machine,
            "exclude_machines": self.exclude_machines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRequirements:
        """Deserialize from dictionary."""
        return cls(
            capabilities=data.get("capabilities", []),
            min_cpu_cores=data.get("min_cpu_cores"),
            min_memory_gb=data.get("min_memory_gb"),
            gpu_required=data.get("gpu_required", False),
            ane_required=data.get("ane_required", False),
            preferred_machine=data.get("preferred_machine"),
            exclude_machines=data.get("exclude_machines", []),
        )


@dataclass
class Job:
    """Job to be dispatched to a machine in the fleet."""

    job_id: str
    job_type: str
    requirements: JobRequirements
    status: JobStatus = JobStatus.PENDING
    assigned_machine: str | None = None
    assigned_node_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    priority: int = 0
    timeout_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "requirements": self.requirements.to_dict(),
            "status": self.status.value,
            "assigned_machine": self.assigned_machine,
            "assigned_node_id": self.assigned_node_id,
            "payload": self.payload,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result": self.result,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """Deserialize from dictionary."""
        return cls(
            job_id=data["job_id"],
            job_type=data["job_type"],
            requirements=JobRequirements.from_dict(data.get("requirements", {})),
            status=JobStatus(data.get("status", "pending")),
            assigned_machine=data.get("assigned_machine"),
            assigned_node_id=data.get("assigned_node_id"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            result=data.get("result"),
            priority=data.get("priority", 0),
            timeout_seconds=data.get("timeout_seconds"),
        )
