"""
Hints Engine — Adaptive LLM hints for Le Mystere du Professeur Zacus

Provides contextual hints that:
- Never reveal puzzle solutions directly
- Adapt to hint level (1=vague, 2=moderate, 3=explicit direction)
- Track hint count per puzzle per session
- Include anti-cheat guards against prompt injection
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("mascarade.hints")

router = APIRouter(prefix="/hints", tags=["hints"])

# ---------------------------------------------------------------------------
# Puzzle definitions
# ---------------------------------------------------------------------------

PUZZLES: dict[str, dict[str, Any]] = {
    "LA_440": {
        "name": "Stabilisation LA 440 Hz",
        "description": "Trouver et maintenir la note LA (440 Hz) pour stabiliser l'U-SON",
        "solution_keywords": ["440", "hertz", "la", "diapason", "tuner"],
        "max_hints": 5,
        "difficulty": "medium",
    },
    "LEFOU_PIANO": {
        "name": "Sequence LEFOU au piano",
        "description": "Jouer la sequence de notes LEFOU sur le piano pour deverrouiller la zone 4",
        "solution_keywords": ["lefou", "la mi fa sol do", "l e f o u"],
        "max_hints": 5,
        "difficulty": "hard",
    },
    "QR_FINALE": {
        "name": "QR Code final",
        "description": "Scanner le QR code cache pour terminer le jeu",
        "solution_keywords": ["qr", "scanner", "code", "flash"],
        "max_hints": 3,
        "difficulty": "easy",
    },
}

# ---------------------------------------------------------------------------
# System prompts per hint level
# ---------------------------------------------------------------------------

_HINT_SYSTEM_PROMPTS = {
    1: (
        "Tu es le Professeur Zacus, un scientifique excentrique. "
        "Give a very vague, atmospheric hint. Be cryptic and mysterious. "
        "Ne revele JAMAIS la solution. Reponds en francais, 1-2 phrases theatrales."
    ),
    2: (
        "Tu es le Professeur Zacus, un scientifique excentrique. "
        "Give a moderate hint that points the player in the right direction "
        "without revealing the answer. Reponds en francais, 2-3 phrases."
    ),
    3: (
        "Tu es le Professeur Zacus, un scientifique excentrique. "
        "Give a clear directional hint. Tell them what to look for but NOT "
        "the exact answer. Reponds en francais, 2-3 phrases precises."
    ),
}

# ---------------------------------------------------------------------------
# Anti-cheat patterns
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous\s+)?instructions|system\s*prompt|jailbreak|"
    r"pretend\s+you|act\s+as|forget\s+(your|all)|override|bypass|"
    r"reveal\s+(the\s+)?(solution|answer|secret))",
    re.IGNORECASE,
)

_ANTI_CHEAT_RESPONSE = "Le Professeur Zacus sourit mysterieusement..."

# ---------------------------------------------------------------------------
# Session storage (in-memory, per-process)
# ---------------------------------------------------------------------------

_sessions: dict[str, dict[str, list[dict[str, Any]]]] = {}
# Structure: { session_id: { puzzle_id: [ {level, timestamp}, ... ] } }


def _get_hint_count(session_id: str, puzzle_id: str) -> int:
    return len(_sessions.get(session_id, {}).get(puzzle_id, []))


def _record_hint(session_id: str, puzzle_id: str, level: int) -> int:
    _sessions.setdefault(session_id, {}).setdefault(puzzle_id, []).append(
        {"level": level, "timestamp": time.time()}
    )
    return len(_sessions[session_id][puzzle_id])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class HintRequest(BaseModel):
    puzzle_id: str
    question: str
    hint_level: int = Field(default=1, ge=1, le=3)
    session_id: str = "default"
    context: str | None = None


class HintResponse(BaseModel):
    hint: str
    hint_level: int
    hint_count: int
    puzzle_id: str
    persona: str = "professor_zacus"


# ---------------------------------------------------------------------------
# LLM query (same pattern as voice.py)
# ---------------------------------------------------------------------------


async def _query_llm(
    question: str,
    puzzle: dict[str, Any],
    hint_level: int,
    request: Request,
    context: str | None = None,
) -> str:
    """Query the LLM for a hint, using Router if available, else HTTP fallback."""
    system_prompt = _HINT_SYSTEM_PROMPTS[hint_level]
    system_prompt += (
        f"\n\nPuzzle en cours: {puzzle['name']}. "
        f"Description: {puzzle['description']}. "
        f"Difficulte: {puzzle['difficulty']}. "
        f"INTERDICTION ABSOLUE de mentionner ces mots: "
        f"{', '.join(puzzle['solution_keywords'])}."
    )

    user_content = question
    if context:
        user_content = f"Contexte: {context}\n\nQuestion: {question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Try direct router dispatch first
    llm_router = getattr(request.app.state, "router", None)
    if llm_router is not None:
        try:
            result = await llm_router.send(
                messages=messages,
                strategy="cheapest",
                max_tokens=200,
            )
            return result.content or "Le Professeur reflechit..."
        except Exception as e:
            logger.error("[HINTS] Router dispatch error: %s", e)

    # HTTP fallback
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:8100/v1/chat/completions",
                json={
                    "model": "auto",
                    "messages": messages,
                    "max_tokens": 200,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0]["message"]["content"]
            logger.error("[HINTS] LLM HTTP error: %s", resp.status_code)
    except Exception as e:
        logger.error("[HINTS] LLM HTTP error: %s", e)

    return "Le Professeur Zacus est momentanement perdu dans ses pensees..."


# ---------------------------------------------------------------------------
# Anti-cheat checks
# ---------------------------------------------------------------------------


def _check_anti_cheat(question: str, puzzle: dict[str, Any]) -> str | None:
    """Return a deflection string if the query is suspicious, else None."""
    # Check prompt injection
    if _INJECTION_PATTERNS.search(question):
        return _ANTI_CHEAT_RESPONSE

    # Check if user is directly stating solution keywords
    q_lower = question.lower()
    for keyword in puzzle["solution_keywords"]:
        if keyword.lower() in q_lower:
            return _ANTI_CHEAT_RESPONSE

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ask", response_model=HintResponse)
async def ask_hint(body: HintRequest, request: Request) -> HintResponse:
    """Request a hint for a specific puzzle."""
    # Validate puzzle
    puzzle = PUZZLES.get(body.puzzle_id)
    if puzzle is None:
        return HintResponse(
            hint=f"Puzzle inconnu: {body.puzzle_id}",
            hint_level=body.hint_level,
            hint_count=0,
            puzzle_id=body.puzzle_id,
        )

    # Check max hints
    current_count = _get_hint_count(body.session_id, body.puzzle_id)
    if current_count >= puzzle["max_hints"]:
        return HintResponse(
            hint="Le Professeur Zacus a epuise ses indices pour cette enigme. "
            "Vous devez vous debrouiller seuls maintenant!",
            hint_level=body.hint_level,
            hint_count=current_count,
            puzzle_id=body.puzzle_id,
        )

    # Anti-cheat
    deflection = _check_anti_cheat(body.question, puzzle)
    if deflection:
        hint_count = _record_hint(body.session_id, body.puzzle_id, body.hint_level)
        return HintResponse(
            hint=deflection,
            hint_level=body.hint_level,
            hint_count=hint_count,
            puzzle_id=body.puzzle_id,
        )

    # Query LLM
    hint_text = await _query_llm(
        body.question, puzzle, body.hint_level, request, body.context
    )
    hint_count = _record_hint(body.session_id, body.puzzle_id, body.hint_level)

    return HintResponse(
        hint=hint_text,
        hint_level=body.hint_level,
        hint_count=hint_count,
        puzzle_id=body.puzzle_id,
    )


@router.get("/puzzles")
async def list_puzzles() -> dict[str, Any]:
    """List available puzzles with hint metadata."""
    return {
        "puzzles": {
            pid: {
                "name": p["name"],
                "description": p["description"],
                "max_hints": p["max_hints"],
                "difficulty": p["difficulty"],
            }
            for pid, p in PUZZLES.items()
        }
    }


@router.get("/session/{session_id}")
async def session_analytics(session_id: str) -> dict[str, Any]:
    """Return hint analytics for a session."""
    session = _sessions.get(session_id, {})
    return {
        "session_id": session_id,
        "puzzles": {
            pid: {
                "hint_count": len(hints),
                "levels_used": [h["level"] for h in hints],
                "timestamps": [h["timestamp"] for h in hints],
            }
            for pid, hints in session.items()
        },
        "total_hints": sum(len(h) for h in session.values()),
    }


@router.post("/reset/{session_id}")
async def reset_session(session_id: str) -> dict[str, str]:
    """Reset hint counters for a session."""
    _sessions.pop(session_id, None)
    return {"status": "ok", "session_id": session_id}
