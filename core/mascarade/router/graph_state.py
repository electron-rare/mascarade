"""
graph_state.py -- Lightweight graph-based state machine for agent orchestration.

Compatible with LangGraph concepts (states, transitions, conditional edges)
but zero external dependency.  Mount on FastAPI via mount_graph_routes().

States:
    IDLE        -> ROUTING
    ROUTING     -> EXECUTING | FAILED
    EXECUTING   -> EVALUATING | FAILED
    EVALUATING  -> ROUTING | COMPLETE | FAILED
    COMPLETE    -> IDLE
    FAILED      -> IDLE

Usage:
    from mascarade.router.graph_state import GraphStateMachine, mount_graph_routes
    gsm = GraphStateMachine()
    gsm.transition("ROUTING")          # IDLE -> ROUTING
    gsm.transition("EXECUTING")        # ROUTING -> EXECUTING
    mount_graph_routes(app, gsm)       # FastAPI GET /v1/graph/state, POST /v1/graph/transition
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

class AgentState(str, Enum):
    IDLE = "IDLE"
    ROUTING = "ROUTING"
    EXECUTING = "EXECUTING"
    EVALUATING = "EVALUATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


# Allowed transitions (directed graph: source -> set of valid targets)
TRANSITIONS: Dict[AgentState, set[AgentState]] = {
    AgentState.IDLE:       {AgentState.ROUTING},
    AgentState.ROUTING:    {AgentState.EXECUTING, AgentState.FAILED},
    AgentState.EXECUTING:  {AgentState.EVALUATING, AgentState.FAILED},
    AgentState.EVALUATING: {AgentState.ROUTING, AgentState.COMPLETE, AgentState.FAILED},
    AgentState.COMPLETE:   {AgentState.IDLE},
    AgentState.FAILED:     {AgentState.IDLE},
}


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------

@dataclass
class TransitionRecord:
    from_state: str
    to_state: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class InvalidTransition(Exception):
    """Raised when a transition is not allowed by the graph."""


class GraphStateMachine:
    """Minimal graph-based state machine for orchestration workflows."""

    def __init__(self, initial: AgentState = AgentState.IDLE) -> None:
        self._state: AgentState = initial
        self._history: List[TransitionRecord] = []
        self._context: Dict[str, Any] = {}

    # -- read --

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def history(self) -> List[TransitionRecord]:
        return list(self._history)

    @property
    def context(self) -> Dict[str, Any]:
        return dict(self._context)

    def allowed_transitions(self) -> List[str]:
        """Return state names reachable from the current state."""
        return sorted(s.value for s in TRANSITIONS.get(self._state, set()))

    # -- write --

    def transition(
        self,
        target: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TransitionRecord:
        """Move to *target* state if the transition is allowed.

        Parameters
        ----------
        target:
            Name of the destination state (case-insensitive).
        metadata:
            Optional dict attached to the transition record.

        Returns
        -------
        TransitionRecord for the completed transition.

        Raises
        ------
        InvalidTransition
            If the transition is not in the allowed graph.
        """
        try:
            target_state = AgentState(target.upper())
        except ValueError:
            raise InvalidTransition(
                f"Unknown state '{target}'. "
                f"Valid states: {[s.value for s in AgentState]}"
            )

        allowed = TRANSITIONS.get(self._state, set())
        if target_state not in allowed:
            raise InvalidTransition(
                f"Cannot transition {self._state.value} -> {target_state.value}. "
                f"Allowed from {self._state.value}: {sorted(s.value for s in allowed)}"
            )

        record = TransitionRecord(
            from_state=self._state.value,
            to_state=target_state.value,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self._state = target_state
        self._history.append(record)
        return record

    def set_context(self, key: str, value: Any) -> None:
        self._context[key] = value

    def reset(self) -> None:
        """Reset to IDLE and clear history / context."""
        self._state = AgentState.IDLE
        self._history.clear()
        self._context.clear()


# ---------------------------------------------------------------------------
# FastAPI integration
# ---------------------------------------------------------------------------

def mount_graph_routes(app: Any, gsm: Optional[GraphStateMachine] = None) -> GraphStateMachine:
    """Add GET /v1/graph/state and POST /v1/graph/transition to a FastAPI app.

    Parameters
    ----------
    app:
        A FastAPI (or Starlette) application instance.
    gsm:
        An existing GraphStateMachine, or None to create a fresh one.

    Returns
    -------
    The GraphStateMachine instance used (handy if auto-created).
    """
    from fastapi import HTTPException
    from pydantic import BaseModel

    if gsm is None:
        gsm = GraphStateMachine()

    class TransitionRequest(BaseModel):
        target: str
        metadata: Optional[Dict[str, Any]] = None

    @app.get("/v1/graph/state")
    async def get_state():
        return {
            "state": gsm.state.value,
            "allowed_transitions": gsm.allowed_transitions(),
            "context": gsm.context,
            "history_length": len(gsm.history),
        }

    @app.post("/v1/graph/transition")
    async def post_transition(req: TransitionRequest):
        try:
            record = gsm.transition(req.target, metadata=req.metadata)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {
            "state": gsm.state.value,
            "transition": {
                "from": record.from_state,
                "to": record.to_state,
                "timestamp": record.timestamp,
                "metadata": record.metadata,
            },
            "allowed_transitions": gsm.allowed_transitions(),
        }

    return gsm
