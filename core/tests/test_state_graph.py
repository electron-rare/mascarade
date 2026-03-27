"""Tests for mascarade.orchestrator.state_graph — 20 tests."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

import pytest

from mascarade.orchestrator.state_graph import END, GraphExecutionError, StateGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inc(state: dict) -> dict:
    return {"counter": state.get("counter", 0) + 1}


async def _async_inc(state: dict) -> dict:
    await asyncio.sleep(0)
    return {"counter": state.get("counter", 0) + 1}


def _tag(label: str):
    """Return a node fn that appends *label* to state['path']."""

    def _fn(state: dict) -> dict:
        path = list(state.get("path", []))
        path.append(label)
        return {"path": path}

    return _fn


# ---------------------------------------------------------------------------
# 1. Linear graph (A -> B -> C)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linear_graph():
    g = StateGraph()
    g.add_node("a", _tag("A"))
    g.add_node("b", _tag("B"))
    g.add_node("c", _tag("C"))
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.set_entry_point("a")
    g.set_finish_point("c")

    result = await g.invoke({"path": []})
    assert result["path"] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# 2. Linear graph preserves extra state keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linear_preserves_state():
    g = StateGraph()
    g.add_node("a", lambda s: {"x": 1})
    g.add_node("b", lambda s: {"y": s["x"] + 1})
    g.add_edge("a", "b")
    g.set_entry_point("a")
    g.set_finish_point("b")

    result = await g.invoke({"seed": 42})
    assert result["seed"] == 42
    assert result["x"] == 1
    assert result["y"] == 2


# ---------------------------------------------------------------------------
# 3. Conditional edges — branch based on state value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conditional_edges():
    g = StateGraph()
    g.add_node("router", lambda s: {})
    g.add_node("pos", lambda s: {"sentiment": "positive"})
    g.add_node("neg", lambda s: {"sentiment": "negative"})

    g.add_conditional_edges(
        "router",
        lambda s: s.get("mood", "good"),
        {"good": "pos", "bad": "neg"},
    )
    g.set_entry_point("router")
    g.set_finish_point("pos")
    g.set_finish_point("neg")

    r1 = await g.invoke({"mood": "good"})
    assert r1["sentiment"] == "positive"

    r2 = await g.invoke({"mood": "bad"})
    assert r2["sentiment"] == "negative"


# ---------------------------------------------------------------------------
# 4. Conditional edge to END
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conditional_edge_to_end():
    g = StateGraph()
    g.add_node("check", _inc)
    g.add_conditional_edges(
        "check",
        lambda s: "done" if s["counter"] >= 1 else "again",
        {"done": END, "again": "check"},
    )
    g.set_entry_point("check")

    result = await g.invoke({"counter": 0})
    assert result["counter"] == 1


# ---------------------------------------------------------------------------
# 5. Cycle with counter — loop until condition met
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cycle_with_counter():
    g = StateGraph()
    g.add_node("step", _inc)
    g.add_conditional_edges(
        "step",
        lambda s: "done" if s["counter"] >= 5 else "loop",
        {"done": END, "loop": "step"},
    )
    g.set_entry_point("step")

    result = await g.invoke({"counter": 0})
    assert result["counter"] == 5


# ---------------------------------------------------------------------------
# 6. Max iterations safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_iterations():
    g = StateGraph(max_iterations=3)
    g.add_node("loop", _inc)
    g.add_edge("loop", "loop")  # infinite loop
    g.set_entry_point("loop")

    with pytest.raises(GraphExecutionError, match="Max iterations"):
        await g.invoke({"counter": 0})


# ---------------------------------------------------------------------------
# 7. Async node functions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_node():
    g = StateGraph()
    g.add_node("a", _async_inc)
    g.add_node("b", _async_inc)
    g.add_edge("a", "b")
    g.set_entry_point("a")
    g.set_finish_point("b")

    result = await g.invoke({"counter": 0})
    assert result["counter"] == 2


# ---------------------------------------------------------------------------
# 8. Mixed sync and async nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_sync_async():
    g = StateGraph()
    g.add_node("sync", _inc)
    g.add_node("async", _async_inc)
    g.add_edge("sync", "async")
    g.set_entry_point("sync")
    g.set_finish_point("async")

    result = await g.invoke({"counter": 0})
    assert result["counter"] == 2


# ---------------------------------------------------------------------------
# 9. Node returning None treated as empty dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_returns_none():
    g = StateGraph()
    g.add_node("noop", lambda s: None)
    g.add_node("inc", _inc)
    g.add_edge("noop", "inc")
    g.set_entry_point("noop")
    g.set_finish_point("inc")

    result = await g.invoke({"counter": 10})
    assert result["counter"] == 11


# ---------------------------------------------------------------------------
# 10. Checkpointing — saves and loads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpointing():
    with tempfile.TemporaryDirectory() as tmpdir:
        g = StateGraph(checkpoint_dir=tmpdir)
        g.add_node("a", _tag("A"))
        g.add_node("b", _tag("B"))
        g.add_edge("a", "b")
        g.set_entry_point("a")
        g.set_finish_point("b")

        run_id = "test-ckpt-001"
        result = await g.invoke({"path": []}, run_id=run_id)
        assert result["path"] == ["A", "B"]

        checkpoint = g.load_checkpoint(run_id)
        assert checkpoint is not None
        assert checkpoint["run_id"] == run_id
        assert checkpoint["state"]["path"] == ["A", "B"]


# ---------------------------------------------------------------------------
# 11. Resume from checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_from_checkpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Manually write a checkpoint to simulate a partial run
        run_id = "test-resume-001"
        ckpt_path = os.path.join(tmpdir, f"{run_id}.json")
        with open(ckpt_path, "w") as fp:
            json.dump(
                {
                    "run_id": run_id,
                    "state": {"counter": 3, "resumed": False},
                    "current_node": "step",
                    "iteration": 3,
                    "timestamp": 0,
                },
                fp,
            )

        g = StateGraph(checkpoint_dir=tmpdir, max_iterations=10)
        g.add_node("step", lambda s: {"counter": s["counter"] + 1, "resumed": True})
        g.add_conditional_edges(
            "step",
            lambda s: "done" if s["counter"] >= 5 else "loop",
            {"done": END, "loop": "step"},
        )
        g.set_entry_point("step")

        result = await g.invoke(
            {"counter": 0},
            run_id=run_id,
            resume=True,
        )
        # Should have resumed from counter=3 and counted to 5
        assert result["counter"] == 5
        assert result["resumed"] is True


# ---------------------------------------------------------------------------
# 12. Streaming output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming():
    g = StateGraph()
    g.add_node("a", _tag("A"))
    g.add_node("b", _tag("B"))
    g.add_node("c", _tag("C"))
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.set_entry_point("a")
    g.set_finish_point("c")

    events: list[tuple[str, dict]] = []
    async for node_name, state in g.stream({"path": []}):
        events.append((node_name, dict(state)))

    assert len(events) == 3
    assert events[0][0] == "a"
    assert events[1][0] == "b"
    assert events[2][0] == "c"
    assert events[2][1]["path"] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# 13. Streaming with cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_cycle():
    g = StateGraph()
    g.add_node("step", _inc)
    g.add_conditional_edges(
        "step",
        lambda s: "done" if s["counter"] >= 3 else "loop",
        {"done": END, "loop": "step"},
    )
    g.set_entry_point("step")

    events = []
    async for node_name, state in g.stream({"counter": 0}):
        events.append((node_name, state["counter"]))

    assert events == [("step", 1), ("step", 2), ("step", 3)]


# ---------------------------------------------------------------------------
# 14. Validation: no entry point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_entry_point():
    g = StateGraph()
    g.add_node("a", _inc)
    with pytest.raises(GraphExecutionError, match="No entry point"):
        await g.invoke({})


# ---------------------------------------------------------------------------
# 15. Validation: entry point not registered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_entry_point():
    g = StateGraph()
    g.add_node("a", _inc)
    g.set_entry_point("nonexistent")
    with pytest.raises(GraphExecutionError, match="not a registered node"):
        await g.invoke({})


# ---------------------------------------------------------------------------
# 16. Duplicate node name raises
# ---------------------------------------------------------------------------


def test_duplicate_node():
    g = StateGraph()
    g.add_node("a", _inc)
    with pytest.raises(ValueError, match="already exists"):
        g.add_node("a", _inc)


# ---------------------------------------------------------------------------
# 17. Cannot use END as node name
# ---------------------------------------------------------------------------


def test_reserved_end_name():
    g = StateGraph()
    with pytest.raises(ValueError, match="reserved"):
        g.add_node(END, _inc)


# ---------------------------------------------------------------------------
# 18. Condition returns unknown key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_condition_unknown_key():
    g = StateGraph()
    g.add_node("router", lambda s: {})
    g.add_conditional_edges(
        "router",
        lambda s: "unknown",
        {"a": "router"},
    )
    g.set_entry_point("router")

    with pytest.raises(GraphExecutionError, match="not in mapping"):
        await g.invoke({})


# ---------------------------------------------------------------------------
# 19. Node returning non-dict raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_returns_non_dict():
    g = StateGraph()
    g.add_node("bad", lambda s: "not a dict")
    g.set_entry_point("bad")
    g.set_finish_point("bad")

    with pytest.raises(GraphExecutionError, match="must return a dict"):
        await g.invoke({})


# ---------------------------------------------------------------------------
# 20. Introspection helpers
# ---------------------------------------------------------------------------


def test_introspection():
    g = StateGraph()
    g.add_node("a", _inc)
    g.add_node("b", _inc)
    g.add_edge("a", "b")

    assert set(g.nodes()) == {"a", "b"}
    assert g.edges() == [("a", "b")]


# ---------------------------------------------------------------------------
# 21. Pydantic state schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pydantic_schema_validation():
    from pydantic import BaseModel

    class MyState(BaseModel):
        counter: int
        label: str = "default"

    g = StateGraph(state_schema=MyState)
    g.add_node("inc", _inc)
    g.set_entry_point("inc")
    g.set_finish_point("inc")

    result = await g.invoke({"counter": 0, "label": "test"})
    assert result["counter"] == 1
    assert result["label"] == "test"


@pytest.mark.asyncio
async def test_pydantic_schema_rejects_invalid():
    from pydantic import BaseModel, ValidationError

    class MyState(BaseModel):
        counter: int

    g = StateGraph(state_schema=MyState)
    g.add_node("inc", _inc)
    g.set_entry_point("inc")
    g.set_finish_point("inc")

    with pytest.raises(ValidationError):
        await g.invoke({"wrong_field": "oops"})


# ---------------------------------------------------------------------------
# 22. Checkpoint absent returns None
# ---------------------------------------------------------------------------


def test_checkpoint_absent():
    with tempfile.TemporaryDirectory() as tmpdir:
        g = StateGraph(checkpoint_dir=tmpdir)
        assert g.load_checkpoint("nonexistent-run") is None


# ---------------------------------------------------------------------------
# 23. No checkpoint_dir means no checkpoint saved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_checkpoint_dir():
    g = StateGraph()  # no checkpoint_dir
    g.add_node("a", _inc)
    g.set_entry_point("a")
    g.set_finish_point("a")

    result = await g.invoke({"counter": 0}, run_id="no-ckpt")
    assert result["counter"] == 1
    assert g.load_checkpoint("no-ckpt") is None
