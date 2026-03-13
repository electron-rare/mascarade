"""Job queue with JSON persistence for multi-machine dispatch."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mascarade.dispatch.models import Job, JobStatus

DEFAULT_DISPATCH_STATE_DIR = os.getenv("DISPATCH_STATE_DIR", "").strip()


class JobQueueError(RuntimeError):
    """Base error for job queue operations."""


class JobNotFoundError(JobQueueError):
    """Raised when a job is not found in the queue."""


def _iso_now() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class JobQueue:
    """Queue for managing jobs with JSON persistence.

    Stores jobs in a JSON file and provides operations for adding,
    retrieving, updating, and removing jobs.
    """

    def __init__(
        self,
        *,
        state_dir: Path | None = None,
        queue_file: str = "job_queue.json",
    ) -> None:
        """Initialize job queue with persistence location.

        Args:
            state_dir: Directory for storing queue state. If None, will auto-resolve.
            queue_file: Name of the JSON file to store queue data.
        """
        self.state_dir = state_dir or self._resolve_state_dir()
        self.queue_file = self.state_dir / queue_file
        self._jobs: dict[str, Job] = {}
        self._load()

    def _resolve_state_dir(self) -> Path:
        """Resolve the state directory for queue persistence.

        Tries multiple locations in order of preference:
        1. DISPATCH_STATE_DIR env var
        2. XDG_STATE_HOME/mascarade/dispatch
        3. ~/.local/state/mascarade/dispatch
        4. /tmp/mascarade/dispatch (fallback)

        Returns:
            Path to writable state directory.
        """
        candidates: list[Path] = []

        # Environment variable override
        if DEFAULT_DISPATCH_STATE_DIR:
            candidates.append(Path(DEFAULT_DISPATCH_STATE_DIR).expanduser())

        # XDG state directory
        xdg_state_home = os.getenv("XDG_STATE_HOME", "").strip()
        if xdg_state_home:
            candidates.append(Path(xdg_state_home) / "mascarade" / "dispatch")

        # User home directory
        home = os.getenv("HOME", "").strip()
        if home:
            candidates.append(
                Path(home).expanduser() / ".local" / "state" / "mascarade" / "dispatch"
            )

        # Temp directory fallback
        candidates.append(Path(tempfile.gettempdir()) / "mascarade" / "dispatch")

        # Try each candidate directory
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                # Test write permissions
                probe = candidate / ".write-test"
                probe.write_text("ok\n", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return candidate
            except OSError:
                continue

        # Final fallback
        fallback = Path(tempfile.gettempdir()) / "mascarade" / "dispatch"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _load(self) -> None:
        """Load queue state from JSON file."""
        if not self.queue_file.exists():
            self._jobs = {}
            return

        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
            self._jobs = {
                job_id: Job.from_dict(job_data)
                for job_id, job_data in data.get("jobs", {}).items()
            }
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise JobQueueError(f"Failed to load queue from {self.queue_file}: {exc}") from exc

    def _persist(self) -> None:
        """Persist queue state to JSON file."""
        try:
            data = {
                "jobs": {job_id: job.to_dict() for job_id, job in self._jobs.items()},
                "last_updated": _iso_now(),
            }
            # Write atomically using a temp file
            temp_file = self.queue_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.replace(self.queue_file)
        except OSError as exc:
            raise JobQueueError(f"Failed to persist queue to {self.queue_file}: {exc}") from exc

    def add_job(self, job: Job) -> None:
        """Add a job to the queue.

        Args:
            job: Job to add.

        Raises:
            JobQueueError: If job already exists or persistence fails.
        """
        if job.job_id in self._jobs:
            raise JobQueueError(f"Job {job.job_id} already exists in queue")

        # Set created_at if not already set
        if job.created_at is None:
            job.created_at = _iso_now()

        # Set initial status to queued if still pending
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.QUEUED

        self._jobs[job.job_id] = job
        self._persist()

    def get_job(self, job_id: str) -> Job:
        """Retrieve a job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            Job object.

        Raises:
            JobNotFoundError: If job is not in queue.
        """
        if job_id not in self._jobs:
            raise JobNotFoundError(f"Job {job_id} not found in queue")
        return self._jobs[job_id]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        assigned_machine: str | None = None,
        assigned_node_id: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> Job:
        """Update job status and related fields.

        Args:
            job_id: Job identifier.
            status: New status.
            assigned_machine: Machine assigned to job (optional).
            assigned_node_id: Node ID assigned to job (optional).
            error: Error message for failed jobs (optional).
            result: Result data for completed jobs (optional).

        Returns:
            Updated job object.

        Raises:
            JobNotFoundError: If job is not in queue.
        """
        job = self.get_job(job_id)
        job.status = status

        if assigned_machine is not None:
            job.assigned_machine = assigned_machine
        if assigned_node_id is not None:
            job.assigned_node_id = assigned_node_id
        if error is not None:
            job.error = error
        if result is not None:
            job.result = result

        # Update timestamps
        now = _iso_now()
        if status == JobStatus.RUNNING and job.started_at is None:
            job.started_at = now
        elif status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            if job.started_at is None:
                job.started_at = now
            job.completed_at = now

        self._persist()
        return job

    def remove_job(self, job_id: str) -> Job:
        """Remove a job from the queue.

        Args:
            job_id: Job identifier.

        Returns:
            Removed job object.

        Raises:
            JobNotFoundError: If job is not in queue.
        """
        job = self.get_job(job_id)
        del self._jobs[job_id]
        self._persist()
        return job

    def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        job_type: str | None = None,
        assigned_machine: str | None = None,
    ) -> list[Job]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status (optional).
            job_type: Filter by job type (optional).
            assigned_machine: Filter by assigned machine (optional).

        Returns:
            List of matching jobs, sorted by priority (highest first) then created_at.
        """
        jobs = list(self._jobs.values())

        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        if job_type is not None:
            jobs = [job for job in jobs if job.job_type == job_type]
        if assigned_machine is not None:
            jobs = [job for job in jobs if job.assigned_machine == assigned_machine]

        # Sort by priority (descending) then created_at (ascending)
        jobs.sort(key=lambda j: (-j.priority, j.created_at or ""))
        return jobs

    def get_pending_jobs(self) -> list[Job]:
        """Get all jobs that are queued and awaiting assignment.

        Returns:
            List of queued jobs, sorted by priority (highest first) then created_at.
        """
        return self.list_jobs(status=JobStatus.QUEUED)

    def get_active_jobs(self) -> list[Job]:
        """Get all jobs that are currently assigned or running.

        Returns:
            List of active jobs.
        """
        jobs = list(self._jobs.values())
        active_statuses = {JobStatus.ASSIGNED, JobStatus.RUNNING}
        return [job for job in jobs if job.status in active_statuses]

    def clear_completed_jobs(self, *, keep_count: int = 100) -> int:
        """Remove old completed/failed/cancelled jobs.

        Keeps the most recent jobs based on completed_at timestamp.

        Args:
            keep_count: Number of completed jobs to retain.

        Returns:
            Number of jobs removed.
        """
        terminal_statuses = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        completed_jobs = [
            job for job in self._jobs.values()
            if job.status in terminal_statuses
        ]

        if len(completed_jobs) <= keep_count:
            return 0

        # Sort by completed_at (most recent first)
        completed_jobs.sort(key=lambda j: j.completed_at or "", reverse=True)

        # Remove jobs beyond keep_count
        jobs_to_remove = completed_jobs[keep_count:]
        for job in jobs_to_remove:
            del self._jobs[job.job_id]

        if jobs_to_remove:
            self._persist()

        return len(jobs_to_remove)

    def size(self) -> int:
        """Return the total number of jobs in the queue.

        Returns:
            Number of jobs.
        """
        return len(self._jobs)

    def clear(self) -> None:
        """Remove all jobs from the queue.

        Warning: This operation cannot be undone.
        """
        self._jobs.clear()
        self._persist()
