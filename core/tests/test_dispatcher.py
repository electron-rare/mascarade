"""Tests for job dispatcher and queue."""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from mascarade.dispatch.dispatcher import (
    Dispatcher,
    MachineProfile,
    NoMachineAvailableError,
)
from mascarade.dispatch.job_queue import JobNotFoundError, JobQueue, JobQueueError
from mascarade.dispatch.models import Job, JobRequirements, JobStatus

# ===========================
# JobQueue Tests
# ===========================


def test_job_queue_initialization():
    """Test that job queue initializes with empty state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))
        assert queue.size() == 0
        assert len(queue.list_jobs()) == 0


def test_job_queue_add_and_get():
    """Test adding and retrieving jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id=str(uuid4()),
            job_type="inference",
            requirements=JobRequirements(capabilities=["gpu"]),
        )

        queue.add_job(job)
        assert queue.size() == 1

        retrieved = queue.get_job(job.job_id)
        assert retrieved.job_id == job.job_id
        assert retrieved.job_type == "inference"
        assert retrieved.status == JobStatus.QUEUED


def test_job_queue_add_sets_created_at_and_status():
    """Test that add_job sets created_at and updates status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id=str(uuid4()),
            job_type="fine_tune",
            requirements=JobRequirements(gpu_required=True),
            status=JobStatus.PENDING,
        )

        assert job.created_at is None
        queue.add_job(job)

        retrieved = queue.get_job(job.job_id)
        assert retrieved.created_at is not None
        assert retrieved.status == JobStatus.QUEUED


def test_job_queue_add_duplicate_raises_error():
    """Test that adding duplicate job raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id="test-job-123",
            job_type="inference",
            requirements=JobRequirements(),
        )

        queue.add_job(job)

        with pytest.raises(JobQueueError, match="already exists"):
            queue.add_job(job)


def test_job_queue_get_nonexistent_raises_error():
    """Test that getting nonexistent job raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        with pytest.raises(JobNotFoundError, match="not found"):
            queue.get_job("nonexistent-job")


def test_job_queue_update_status():
    """Test updating job status and timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id=str(uuid4()),
            job_type="inference",
            requirements=JobRequirements(),
        )
        queue.add_job(job)

        # Update to assigned
        updated = queue.update_job_status(
            job.job_id,
            JobStatus.ASSIGNED,
            assigned_machine="gpu-machine",
            assigned_node_id="node-gpu",
        )
        assert updated.status == JobStatus.ASSIGNED
        assert updated.assigned_machine == "gpu-machine"
        assert updated.assigned_node_id == "node-gpu"

        # Update to running (should set started_at)
        updated = queue.update_job_status(job.job_id, JobStatus.RUNNING)
        assert updated.status == JobStatus.RUNNING
        assert updated.started_at is not None

        # Update to completed (should set completed_at)
        updated = queue.update_job_status(
            job.job_id,
            JobStatus.COMPLETED,
            result={"output": "success"},
        )
        assert updated.status == JobStatus.COMPLETED
        assert updated.completed_at is not None
        assert updated.result == {"output": "success"}


def test_job_queue_update_failed_with_error():
    """Test updating job to failed status with error message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id=str(uuid4()),
            job_type="fine_tune",
            requirements=JobRequirements(),
        )
        queue.add_job(job)

        updated = queue.update_job_status(
            job.job_id,
            JobStatus.FAILED,
            error="GPU out of memory",
        )
        assert updated.status == JobStatus.FAILED
        assert updated.error == "GPU out of memory"
        assert updated.completed_at is not None


def test_job_queue_remove():
    """Test removing a job from the queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job = Job(
            job_id=str(uuid4()),
            job_type="inference",
            requirements=JobRequirements(),
        )
        queue.add_job(job)
        assert queue.size() == 1

        removed = queue.remove_job(job.job_id)
        assert removed.job_id == job.job_id
        assert queue.size() == 0

        with pytest.raises(JobNotFoundError):
            queue.get_job(job.job_id)


def test_job_queue_list_with_filters():
    """Test listing jobs with various filters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        # Add jobs with different attributes
        job1 = Job(
            job_id="job-1",
            job_type="inference",
            requirements=JobRequirements(),
            priority=10,
        )
        job2 = Job(
            job_id="job-2",
            job_type="fine_tune",
            requirements=JobRequirements(),
            priority=5,
        )
        job3 = Job(
            job_id="job-3",
            job_type="inference",
            requirements=JobRequirements(),
            priority=15,
        )

        queue.add_job(job1)
        queue.add_job(job2)
        queue.add_job(job3)

        # Update one to running
        queue.update_job_status("job-2", JobStatus.RUNNING, assigned_machine="gpu-1")

        # Test filtering by status
        queued = queue.list_jobs(status=JobStatus.QUEUED)
        assert len(queued) == 2
        assert all(j.status == JobStatus.QUEUED for j in queued)

        # Test filtering by job_type
        inference_jobs = queue.list_jobs(job_type="inference")
        assert len(inference_jobs) == 2
        assert all(j.job_type == "inference" for j in inference_jobs)

        # Test filtering by assigned_machine
        machine_jobs = queue.list_jobs(assigned_machine="gpu-1")
        assert len(machine_jobs) == 1
        assert machine_jobs[0].job_id == "job-2"

        # Test priority sorting (highest first)
        all_jobs = queue.list_jobs()
        priorities = [j.priority for j in all_jobs]
        assert priorities == [15, 10, 5]  # Sorted descending


def test_job_queue_get_pending_jobs():
    """Test getting pending (queued) jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job1 = Job(
            job_id="job-1",
            job_type="inference",
            requirements=JobRequirements(),
            priority=10,
        )
        job2 = Job(
            job_id="job-2",
            job_type="fine_tune",
            requirements=JobRequirements(),
            priority=20,
        )

        queue.add_job(job1)
        queue.add_job(job2)

        # Mark one as running
        queue.update_job_status("job-1", JobStatus.RUNNING)

        pending = queue.get_pending_jobs()
        assert len(pending) == 1
        assert pending[0].job_id == "job-2"
        assert pending[0].status == JobStatus.QUEUED


def test_job_queue_get_active_jobs():
    """Test getting active (assigned or running) jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        job1 = Job(job_id="job-1", job_type="inference", requirements=JobRequirements())
        job2 = Job(job_id="job-2", job_type="fine_tune", requirements=JobRequirements())
        job3 = Job(job_id="job-3", job_type="inference", requirements=JobRequirements())

        queue.add_job(job1)
        queue.add_job(job2)
        queue.add_job(job3)

        queue.update_job_status("job-1", JobStatus.ASSIGNED)
        queue.update_job_status("job-2", JobStatus.RUNNING)
        queue.update_job_status("job-3", JobStatus.COMPLETED)

        active = queue.get_active_jobs()
        assert len(active) == 2
        active_ids = {j.job_id for j in active}
        assert active_ids == {"job-1", "job-2"}


def test_job_queue_clear_completed_jobs():
    """Test clearing old completed jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        # Add multiple completed jobs
        for i in range(10):
            job = Job(
                job_id=f"job-{i}",
                job_type="inference",
                requirements=JobRequirements(),
            )
            queue.add_job(job)
            queue.update_job_status(job.job_id, JobStatus.COMPLETED)

        assert queue.size() == 10

        # Clear, keeping only 5
        removed = queue.clear_completed_jobs(keep_count=5)
        assert removed == 5
        assert queue.size() == 5


def test_job_queue_clear_completed_respects_status():
    """Test that clear_completed_jobs only removes terminal statuses."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        # Add jobs with various statuses
        completed = Job(job_id="completed", job_type="inference", requirements=JobRequirements())
        failed = Job(job_id="failed", job_type="inference", requirements=JobRequirements())
        cancelled = Job(job_id="cancelled", job_type="inference", requirements=JobRequirements())
        running = Job(job_id="running", job_type="inference", requirements=JobRequirements())

        queue.add_job(completed)
        queue.add_job(failed)
        queue.add_job(cancelled)
        queue.add_job(running)

        queue.update_job_status("completed", JobStatus.COMPLETED)
        queue.update_job_status("failed", JobStatus.FAILED)
        queue.update_job_status("cancelled", JobStatus.CANCELLED)
        queue.update_job_status("running", JobStatus.RUNNING)

        # Clear keeping 1 completed job
        removed = queue.clear_completed_jobs(keep_count=1)
        assert removed == 2  # Should remove 2 of 3 terminal jobs
        assert queue.size() == 2  # 1 terminal + 1 running


def test_job_queue_persistence():
    """Test that jobs persist across queue instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)

        # Create queue and add jobs
        queue1 = JobQueue(state_dir=state_dir)
        job1 = Job(
            job_id="persist-1",
            job_type="inference",
            requirements=JobRequirements(capabilities=["gpu"]),
        )
        job2 = Job(
            job_id="persist-2",
            job_type="fine_tune",
            requirements=JobRequirements(gpu_required=True),
        )
        queue1.add_job(job1)
        queue1.add_job(job2)

        # Create new queue instance
        queue2 = JobQueue(state_dir=state_dir)

        # Jobs should be loaded from disk
        assert queue2.size() == 2
        retrieved1 = queue2.get_job("persist-1")
        assert retrieved1.job_type == "inference"
        retrieved2 = queue2.get_job("persist-2")
        assert retrieved2.requirements.gpu_required is True


def test_job_queue_clear():
    """Test clearing all jobs from queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = JobQueue(state_dir=Path(tmpdir))

        for i in range(5):
            job = Job(
                job_id=f"job-{i}",
                job_type="inference",
                requirements=JobRequirements(),
            )
            queue.add_job(job)

        assert queue.size() == 5
        queue.clear()
        assert queue.size() == 0


# ===========================
# Dispatcher Tests
# ===========================


def _make_test_profiles() -> dict[str, MachineProfile]:
    """Create test machine profiles."""
    return {
        "gpu-workstation": MachineProfile(
            machine_id="gpu-workstation",
            aliases={"gpu-workstation", "gpu-ws", "workstation"},
            capabilities={"gpu", "cuda", "nvidia", "rtx", "linux"},
        ),
        "mac-studio": MachineProfile(
            machine_id="mac-studio",
            aliases={"mac-studio", "studio", "ane-mac"},
            capabilities={"ane", "apple-neural-engine", "apple-silicon", "macos"},
        ),
        "cpu-server": MachineProfile(
            machine_id="cpu-server",
            aliases={"cpu-server", "server"},
            capabilities={"cpu", "linux", "docker"},
        ),
    }


def test_dispatcher_initialization():
    """Test dispatcher initialization with pre-loaded profiles."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    assert dispatcher.machine_count() == 3
    assert len(dispatcher.list_machines()) == 3


def test_dispatcher_load_from_json():
    """Test loading machine profiles from JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_file = Path(tmpdir) / "profiles.json"
        profiles_data = {
            "machines": {
                "test-gpu": {
                    "aliases": ["gpu-1", "test-gpu"],
                    "capabilities": ["GPU", "CUDA", "Linux"],
                },
                "test-cpu": {
                    "aliases": ["cpu-1"],
                    "capabilities": ["CPU", "Docker"],
                },
            }
        }
        profiles_file.write_text(json.dumps(profiles_data), encoding="utf-8")

        dispatcher = Dispatcher(profiles_path=profiles_file)

        assert dispatcher.machine_count() == 2
        gpu_profile = dispatcher.get_machine_profile("test-gpu")
        assert gpu_profile is not None
        assert "gpu" in gpu_profile.capabilities  # Should be lowercased
        assert "cuda" in gpu_profile.capabilities


def test_dispatcher_load_missing_file_warns():
    """Test that missing profiles file results in empty dispatcher."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "missing.json"
        dispatcher = Dispatcher(profiles_path=nonexistent)

        assert dispatcher.machine_count() == 0


def test_dispatcher_get_profile_by_alias():
    """Test getting machine profile by alias."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # Direct lookup
    profile = dispatcher.get_machine_profile("gpu-workstation")
    assert profile is not None
    assert profile.machine_id == "gpu-workstation"

    # Lookup by alias
    profile_alias = dispatcher.get_machine_profile("gpu-ws")
    assert profile_alias is not None
    assert profile_alias.machine_id == "gpu-workstation"

    # Nonexistent
    assert dispatcher.get_machine_profile("nonexistent") is None


def test_machine_profile_matches_requirements():
    """Test capability matching for machine profiles."""
    gpu_profile = MachineProfile(
        machine_id="gpu-1",
        aliases={"gpu-1"},
        capabilities={"gpu", "cuda", "nvidia"},
    )

    # Should match GPU requirements
    gpu_req = JobRequirements(gpu_required=True)
    assert gpu_profile.matches_requirements(gpu_req)

    # Should match capability list
    cap_req = JobRequirements(capabilities=["cuda"])
    assert gpu_profile.matches_requirements(cap_req)

    # Should not match ANE requirements
    ane_req = JobRequirements(ane_required=True)
    assert not gpu_profile.matches_requirements(ane_req)

    # Should not match missing capability
    missing_req = JobRequirements(capabilities=["ane"])
    assert not gpu_profile.matches_requirements(missing_req)


def test_machine_profile_score_for_job():
    """Test job scoring for machine profiles."""
    gpu_profile = MachineProfile(
        machine_id="gpu-1",
        aliases={"gpu-1"},
        capabilities={"gpu", "cuda", "nvidia"},
    )

    # Job requiring GPU should get high score
    gpu_job = Job(
        job_id="job-1",
        job_type="fine_tune",
        requirements=JobRequirements(gpu_required=True),
    )
    score = gpu_profile.score_for_job(gpu_job)
    assert score > 50.0

    # Job with preferred machine should get bonus
    preferred_job = Job(
        job_id="job-2",
        job_type="inference",
        requirements=JobRequirements(preferred_machine="gpu-1"),
    )
    preferred_score = gpu_profile.score_for_job(preferred_job)
    assert preferred_score > score  # Should have higher score due to preference

    # Job requiring ANE should get zero score
    ane_job = Job(
        job_id="job-3",
        job_type="inference",
        requirements=JobRequirements(ane_required=True),
    )
    assert gpu_profile.score_for_job(ane_job) == 0.0


def test_dispatcher_find_candidates():
    """Test finding candidate machines for a job."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # Job requiring GPU
    gpu_job = Job(
        job_id="job-1",
        job_type="fine_tune",
        requirements=JobRequirements(gpu_required=True),
    )
    candidates = dispatcher.find_candidates(gpu_job)

    assert len(candidates) == 1
    assert candidates[0].machine_id == "gpu-workstation"
    assert candidates[0].score > 0

    # Job requiring ANE
    ane_job = Job(
        job_id="job-2",
        job_type="inference",
        requirements=JobRequirements(ane_required=True),
    )
    ane_candidates = dispatcher.find_candidates(ane_job)

    assert len(ane_candidates) == 1
    assert ane_candidates[0].machine_id == "mac-studio"

    # Job with no specific requirements (all machines match)
    generic_job = Job(
        job_id="job-3",
        job_type="inference",
        requirements=JobRequirements(),
    )
    generic_candidates = dispatcher.find_candidates(generic_job)

    assert len(generic_candidates) == 3  # All machines should match


def test_dispatcher_find_candidates_with_exclusions():
    """Test that excluded machines are filtered out."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(exclude_machines=["gpu-workstation", "mac-studio"]),
    )
    candidates = dispatcher.find_candidates(job)

    assert len(candidates) == 1
    assert candidates[0].machine_id == "cpu-server"


def test_dispatcher_find_candidates_with_available_filter():
    """Test filtering candidates by available machines list."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(),
    )

    # Restrict to only GPU and CPU machines
    candidates = dispatcher.find_candidates(
        job,
        available_machines=["gpu-workstation", "cpu-server"],
    )

    assert len(candidates) == 2
    machine_ids = {c.machine_id for c in candidates}
    assert machine_ids == {"gpu-workstation", "cpu-server"}


def test_dispatcher_select_machine():
    """Test selecting the best machine for a job."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # GPU job should select GPU machine
    gpu_job = Job(
        job_id="job-1",
        job_type="fine_tune",
        requirements=JobRequirements(gpu_required=True),
    )
    selected = dispatcher.select_machine(gpu_job)
    assert selected == "gpu-workstation"

    # ANE job should select Mac
    ane_job = Job(
        job_id="job-2",
        job_type="inference",
        requirements=JobRequirements(ane_required=True),
    )
    selected = dispatcher.select_machine(ane_job)
    assert selected == "mac-studio"


def test_dispatcher_select_machine_with_preferred():
    """Test that preferred machine is selected when available."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # Job prefers CPU server
    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(preferred_machine="cpu-server"),
    )
    selected = dispatcher.select_machine(job)
    assert selected == "cpu-server"

    # Job prefers by alias
    job_alias = Job(
        job_id="job-2",
        job_type="inference",
        requirements=JobRequirements(preferred_machine="studio"),
    )
    selected = dispatcher.select_machine(job_alias)
    assert selected == "mac-studio"


def test_dispatcher_select_machine_no_match_raises():
    """Test that selecting machine with no match raises error."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # Job requires capability that no machine has
    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(capabilities=["quantum-processor"]),
    )

    with pytest.raises(NoMachineAvailableError, match="No suitable machine"):
        dispatcher.select_machine(job)


def test_dispatcher_select_machine_all_excluded_raises():
    """Test that excluding all machines raises error."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(
            exclude_machines=["gpu-workstation", "mac-studio", "cpu-server"]
        ),
    )

    with pytest.raises(NoMachineAvailableError):
        dispatcher.select_machine(job)


def test_dispatcher_reload_profiles():
    """Test reloading machine profiles from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_file = Path(tmpdir) / "profiles.json"

        # Initial profiles
        initial_data = {
            "machines": {
                "machine-1": {
                    "aliases": ["m1"],
                    "capabilities": ["cpu"],
                }
            }
        }
        profiles_file.write_text(json.dumps(initial_data), encoding="utf-8")

        dispatcher = Dispatcher(profiles_path=profiles_file)
        assert dispatcher.machine_count() == 1

        # Update profiles file
        updated_data = {
            "machines": {
                "machine-1": {
                    "aliases": ["m1"],
                    "capabilities": ["cpu"],
                },
                "machine-2": {
                    "aliases": ["m2"],
                    "capabilities": ["gpu"],
                },
            }
        }
        profiles_file.write_text(json.dumps(updated_data), encoding="utf-8")

        # Reload
        dispatcher.reload_profiles()
        assert dispatcher.machine_count() == 2


def test_dispatcher_to_dict():
    """Test serializing dispatcher state."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    state = dispatcher.to_dict()

    assert "machine_count" in state
    assert state["machine_count"] == 3
    assert "machines" in state
    assert len(state["machines"]) == 3

    # Check that capabilities are serialized
    gpu_machine = next(m for m in state["machines"] if m["machine_id"] == "gpu-workstation")
    assert "gpu" in gpu_machine["capabilities"]
    assert "cuda" in gpu_machine["capabilities"]


def test_job_requirements_matches_capabilities():
    """Test capability matching in JobRequirements."""
    req = JobRequirements(capabilities=["gpu", "cuda"])

    assert req.matches_capabilities(["gpu", "cuda", "nvidia"])  # Has all required
    assert req.matches_capabilities(["gpu", "cuda"])  # Exact match
    assert not req.matches_capabilities(["gpu"])  # Missing cuda
    assert not req.matches_capabilities([])  # Missing all

    # Empty requirements should match anything
    empty_req = JobRequirements()
    assert empty_req.matches_capabilities([])
    assert empty_req.matches_capabilities(["any", "capability"])


def test_job_and_requirements_serialization():
    """Test serialization and deserialization of Job and JobRequirements."""
    requirements = JobRequirements(
        capabilities=["gpu", "cuda"],
        min_cpu_cores=8,
        min_memory_gb=16,
        gpu_required=True,
        ane_required=False,
        preferred_machine="gpu-1",
        exclude_machines=["cpu-1"],
    )

    job = Job(
        job_id="test-job",
        job_type="fine_tune",
        requirements=requirements,
        status=JobStatus.QUEUED,
        priority=10,
        timeout_seconds=3600,
        payload={"model": "gpt-4"},
    )

    # Serialize
    job_dict = job.to_dict()
    assert job_dict["job_id"] == "test-job"
    assert job_dict["requirements"]["capabilities"] == ["gpu", "cuda"]
    assert job_dict["priority"] == 10

    # Deserialize
    restored_job = Job.from_dict(job_dict)
    assert restored_job.job_id == job.job_id
    assert restored_job.requirements.capabilities == job.requirements.capabilities
    assert restored_job.requirements.gpu_required is True
    assert restored_job.requirements.preferred_machine == "gpu-1"
    assert restored_job.priority == 10
    assert restored_job.payload == {"model": "gpt-4"}


def test_candidate_sorting_by_score():
    """Test that candidates are sorted by score (highest first)."""
    profiles = _make_test_profiles()
    dispatcher = Dispatcher(machine_profiles=profiles)

    # Job that prefers GPU but doesn't require it
    job = Job(
        job_id="job-1",
        job_type="inference",
        requirements=JobRequirements(preferred_machine="gpu-workstation"),
    )

    candidates = dispatcher.find_candidates(job)

    # GPU should be first due to preference
    assert len(candidates) > 0
    assert candidates[0].machine_id == "gpu-workstation"

    # Scores should be in descending order
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)
