"""Provider REST pour Quilter — autorouting de PCB.

Actions:
    submit_job      — soumettre un job d'autorouting
    check_status    — polling du job
    list_candidates — lister les candidats de routage
    download_result — telecharger le resultat route
    set_constraints — definir les contraintes de routage
    get_stackup     — obtenir le stackup et impedances
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.providers.quilter")

# ---------------------------------------------------------------------------
# Impedance presets
# ---------------------------------------------------------------------------

IMPEDANCE_PRESETS: dict[str, dict[str, Any]] = {
    "50ohm_single": {
        "name": "50 Ohm Single-Ended",
        "type": "single_ended",
        "target_ohm": 50,
        "tolerance_pct": 10,
        "trace_width_mm": 0.2,
        "dielectric_thickness_mm": 0.2,
        "dielectric_constant": 4.5,
    },
    "100ohm_diff": {
        "name": "100 Ohm Differential",
        "type": "differential",
        "target_ohm": 100,
        "tolerance_pct": 10,
        "trace_width_mm": 0.127,
        "trace_spacing_mm": 0.127,
        "dielectric_thickness_mm": 0.2,
        "dielectric_constant": 4.5,
    },
    "jlc2313": {
        "name": "JLCPCB JLC2313 4-Layer",
        "type": "stackup",
        "layers": [
            {"name": "F.Cu", "thickness_mm": 0.035, "type": "copper"},
            {"name": "Prepreg", "thickness_mm": 0.2, "type": "dielectric", "dk": 4.5},
            {"name": "In1.Cu", "thickness_mm": 0.0175, "type": "copper"},
            {"name": "Core", "thickness_mm": 1.065, "type": "dielectric", "dk": 4.6},
            {"name": "In2.Cu", "thickness_mm": 0.0175, "type": "copper"},
            {"name": "Prepreg", "thickness_mm": 0.2, "type": "dielectric", "dk": 4.5},
            {"name": "B.Cu", "thickness_mm": 0.035, "type": "copper"},
        ],
        "impedance_profiles": {
            "single_50": {"trace_width_mm": 0.224, "reference": "In1.Cu"},
            "diff_100": {"trace_width_mm": 0.127, "spacing_mm": 0.127, "reference": "In1.Cu"},
        },
        "total_thickness_mm": 1.6,
    },
}

ACTIONS = [
    "submit_job",
    "check_status",
    "list_candidates",
    "download_result",
    "set_constraints",
    "get_stackup",
]


class QuilterProvider(LLMProvider):
    """Provider REST pour le service Quilter autorouting.

    Le message utilisateur doit etre un JSON avec un champ ``action``.

    Exemple::

        provider = QuilterProvider()
        response = await provider.send([{
            "role": "user",
            "content": json.dumps({
                "action": "submit_job",
                "file_path": "/tmp/board.kicad_pcb",
                "impedance_preset": "jlc2313",
            })
        }])
    """

    name = "quilter"
    default_model = "quilter-v1"
    cost_per_million = (0.0, 0.0)
    speed_rank = 5
    quality_rank = 8

    def __init__(self, api_url: str | None = None, timeout: float = 120.0):
        self.api_url = (api_url or os.environ.get("QUILTER_API_URL", "")).rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # -- helpers -------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self.api_url)

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=self.timeout,
            )
        return self._client

    async def _post(self, path: str, payload: dict) -> dict:
        client = self._ensure_client()
        resp = await client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        client = self._ensure_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    # -- dispatch ------------------------------------------------------------

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_msg = messages[-1]["content"] if messages else ""

        try:
            request = json.loads(last_msg)
        except (json.JSONDecodeError, TypeError):
            return LLMResponse(
                content=json.dumps({"error": "Expected JSON with 'action' field", "supported_actions": ACTIONS}),
                model=self.default_model,
                provider=self.name,
            )

        action = request.get("action", "")
        handler = {
            "submit_job": self._submit_job,
            "check_status": self._check_status,
            "list_candidates": self._list_candidates,
            "download_result": self._download_result,
            "set_constraints": self._set_constraints,
            "get_stackup": self._get_stackup,
        }.get(action)

        if handler is None:
            result = {"error": f"Unknown action: {action}", "supported_actions": ACTIONS}
        else:
            try:
                result = await handler(request)
            except httpx.HTTPStatusError as exc:
                logger.exception("Quilter API error")
                result = {"error": str(exc), "status_code": exc.response.status_code}
            except Exception as exc:
                logger.exception("Quilter action failed")
                result = {"error": str(exc)}

        return LLMResponse(
            content=json.dumps(result, default=str),
            model=model or self.default_model,
            provider=self.name,
        )

    # -- actions -------------------------------------------------------------

    async def _submit_job(self, request: dict) -> dict:
        file_path = request.get("file_path")
        if not file_path:
            return {"error": "file_path required"}

        impedance_preset = request.get("impedance_preset")
        impedance = None
        if impedance_preset:
            impedance = IMPEDANCE_PRESETS.get(impedance_preset)
            if impedance is None:
                return {"error": f"Unknown impedance preset: {impedance_preset}", "available": list(IMPEDANCE_PRESETS)}

        payload = {
            "file_path": file_path,
            "impedance": impedance,
            "constraints": request.get("constraints", {}),
            "options": request.get("options", {}),
        }
        return await self._post("/v1/jobs", payload)

    async def _check_status(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        return await self._get(f"/v1/jobs/{job_id}/status")

    async def _list_candidates(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        return await self._get(f"/v1/jobs/{job_id}/candidates")

    async def _download_result(self, request: dict) -> dict:
        job_id = request.get("job_id")
        candidate_id = request.get("candidate_id", "best")
        if not job_id:
            return {"error": "job_id required"}

        payload = {
            "candidate_id": candidate_id,
            "format": request.get("format", "kicad_pcb"),
            "output_path": request.get("output_path"),
        }
        return await self._post(f"/v1/jobs/{job_id}/download", payload)

    async def _set_constraints(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}

        constraints = request.get("constraints", {})
        if not constraints:
            return {"error": "constraints dict required"}

        return await self._post(f"/v1/jobs/{job_id}/constraints", constraints)

    async def _get_stackup(self, request: dict) -> dict:
        preset = request.get("preset")
        if preset:
            stackup = IMPEDANCE_PRESETS.get(preset)
            if stackup is None:
                return {"error": f"Unknown preset: {preset}", "available": list(IMPEDANCE_PRESETS)}
            return {"preset": preset, "stackup": stackup}
        return {"presets": IMPEDANCE_PRESETS}

    # -- stream / models -----------------------------------------------------

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        response = await self.send(messages, model=model, system=system, temperature=temperature, max_tokens=max_tokens)
        yield response.content

    def available_models(self) -> list[str]:
        return ["quilter-v1"]
