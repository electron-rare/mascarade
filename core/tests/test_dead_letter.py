"""Tests pour le stockage dead letter."""

import threading
import time

from mascarade.orchestrator.dead_letter import DeadLetterEntry, DeadLetterStore


def test_record_failure_creates_entry():
    store = DeadLetterStore()
    entry = store.record_failure(
        run_id="run-123",
        error="Test error",
        context={"input": "test"},
        mode="sequential",
    )

    assert entry.id
    assert entry.ts
    assert entry.run_id == "run-123"
    assert entry.error == "Test error"
    assert entry.mode == "sequential"
    assert entry.context == {"input": "test"}
    assert entry.agent_name is None
    assert entry.step is None


def test_record_failure_with_all_fields():
    store = DeadLetterStore()
    entry = store.record_failure(
        run_id="run-456",
        error="Agent failed",
        context={"input": "test", "output": "partial"},
        mode="pipeline",
        agent_name="analyst",
        step=2,
        provider="openai",
        model="gpt-4",
    )

    assert entry.run_id == "run-456"
    assert entry.error == "Agent failed"
    assert entry.mode == "pipeline"
    assert entry.agent_name == "analyst"
    assert entry.step == 2
    assert entry.provider == "openai"
    assert entry.model == "gpt-4"


def test_count_returns_entry_count():
    store = DeadLetterStore()
    assert store.count() == 0

    store.record_failure(run_id="run-1", error="error 1", context={})
    assert store.count() == 1

    store.record_failure(run_id="run-2", error="error 2", context={})
    assert store.count() == 2


def test_get_retrieves_entry_by_id():
    store = DeadLetterStore()
    entry1 = store.record_failure(run_id="run-1", error="error 1", context={})
    entry2 = store.record_failure(run_id="run-2", error="error 2", context={})

    retrieved = store.get(entry1.id)
    assert retrieved is not None
    assert retrieved.id == entry1.id
    assert retrieved.run_id == "run-1"

    retrieved2 = store.get(entry2.id)
    assert retrieved2 is not None
    assert retrieved2.run_id == "run-2"


def test_get_returns_none_for_unknown_id():
    store = DeadLetterStore()
    store.record_failure(run_id="run-1", error="error 1", context={})

    retrieved = store.get("nonexistent-id")
    assert retrieved is None


def test_recent_returns_latest_entries():
    store = DeadLetterStore()
    for i in range(5):
        store.record_failure(run_id=f"run-{i}", error=f"error {i}", context={})

    recent = store.recent(limit=3)
    assert len(recent) == 3
    assert recent[0].run_id == "run-2"
    assert recent[1].run_id == "run-3"
    assert recent[2].run_id == "run-4"


def test_recent_filters_by_run_id():
    store = DeadLetterStore()
    store.record_failure(run_id="run-a", error="error 1", context={})
    store.record_failure(run_id="run-b", error="error 2", context={})
    store.record_failure(run_id="run-a", error="error 3", context={})

    filtered = store.recent(run_id="run-a")
    assert len(filtered) == 2
    assert all(entry.run_id == "run-a" for entry in filtered)


def test_recent_filters_by_agent_name():
    store = DeadLetterStore()
    store.record_failure(
        run_id="run-1", error="error 1", context={}, agent_name="analyst"
    )
    store.record_failure(
        run_id="run-2", error="error 2", context={}, agent_name="writer"
    )
    store.record_failure(
        run_id="run-3", error="error 3", context={}, agent_name="analyst"
    )

    filtered = store.recent(agent_name="analyst")
    assert len(filtered) == 2
    assert all(entry.agent_name == "analyst" for entry in filtered)


def test_recent_filters_by_both_run_id_and_agent_name():
    store = DeadLetterStore()
    store.record_failure(
        run_id="run-a", error="error 1", context={}, agent_name="analyst"
    )
    store.record_failure(
        run_id="run-a", error="error 2", context={}, agent_name="writer"
    )
    store.record_failure(
        run_id="run-b", error="error 3", context={}, agent_name="analyst"
    )

    filtered = store.recent(run_id="run-a", agent_name="analyst")
    assert len(filtered) == 1
    assert filtered[0].run_id == "run-a"
    assert filtered[0].agent_name == "analyst"


def test_recent_respects_limit():
    store = DeadLetterStore()
    for i in range(100):
        store.record_failure(run_id=f"run-{i}", error=f"error {i}", context={})

    recent = store.recent(limit=10)
    assert len(recent) == 10


def test_clear_removes_all_entries():
    store = DeadLetterStore()
    store.record_failure(run_id="run-1", error="error 1", context={})
    store.record_failure(run_id="run-2", error="error 2", context={})
    assert store.count() == 2

    store.clear()
    assert store.count() == 0
    assert store.recent() == []


def test_max_entries_limit_enforced():
    store = DeadLetterStore(max_entries=3)

    store.record_failure(run_id="run-1", error="error 1", context={})
    store.record_failure(run_id="run-2", error="error 2", context={})
    store.record_failure(run_id="run-3", error="error 3", context={})
    assert store.count() == 3

    # Adding a 4th entry should evict the oldest
    store.record_failure(run_id="run-4", error="error 4", context={})
    assert store.count() == 3

    recent = store.recent(limit=10)
    run_ids = [entry.run_id for entry in recent]
    assert "run-1" not in run_ids
    assert "run-2" in run_ids
    assert "run-3" in run_ids
    assert "run-4" in run_ids


def test_entry_to_dict_serialization():
    entry = DeadLetterEntry(
        id="test-id",
        ts="2026-03-15T10:00:00Z",
        run_id="run-123",
        error="Test error",
        mode="sequential",
        context={"input": "test"},
        agent_name="analyst",
        step=1,
        provider="openai",
        model="gpt-4",
    )

    data = entry.to_dict()
    assert data["id"] == "test-id"
    assert data["ts"] == "2026-03-15T10:00:00Z"
    assert data["run_id"] == "run-123"
    assert data["error"] == "Test error"
    assert data["mode"] == "sequential"
    assert data["context"] == {"input": "test"}
    assert data["agent_name"] == "analyst"
    assert data["step"] == 1
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4"


def test_thread_safety_concurrent_writes():
    store = DeadLetterStore()
    results = []

    def write_entries(thread_id: int) -> None:
        for i in range(10):
            entry = store.record_failure(
                run_id=f"run-{thread_id}-{i}",
                error=f"error from thread {thread_id}",
                context={},
            )
            results.append(entry)

    threads = [threading.Thread(target=write_entries, args=(i,)) for i in range(5)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # All 50 entries should be recorded
    assert store.count() == 50
    assert len(results) == 50

    # All entry IDs should be unique
    entry_ids = [entry.id for entry in results]
    assert len(entry_ids) == len(set(entry_ids))


def test_thread_safety_concurrent_reads_and_writes():
    store = DeadLetterStore()
    errors = []

    def writer() -> None:
        for i in range(20):
            try:
                store.record_failure(
                    run_id=f"run-{i}",
                    error=f"error {i}",
                    context={},
                )
                time.sleep(0.001)
            except Exception as e:
                errors.append(e)

    def reader() -> None:
        for _ in range(20):
            try:
                store.recent(limit=10)
                store.count()
                time.sleep(0.001)
            except Exception as e:
                errors.append(e)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(errors) == 0
