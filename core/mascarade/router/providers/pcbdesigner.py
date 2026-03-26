"""Provider REST pour PCB Designer AI — conception et fabrication de PCB.

Actions:
    upload_design  — envoyer un .kicad_pcb / .kicad_sch au service
    check_status   — polling du job de design
    export_gerber  — exporter les fichiers Gerber
    order_pcb      — lancer une commande de fabrication
    get_rules      — obtenir les presets de design rules (JLCPCB, PCBWay)
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mascarade.router.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("mascarade.providers.pcbdesigner")

# ---------------------------------------------------------------------------
# Design-rule presets
# ---------------------------------------------------------------------------

DESIGN_RULES: dict[str, dict[str, Any]] = {
    "jlcpcb_2layer": {
        "name": "JLCPCB 2-Layer",
        "layers": 2,
        "min_trace_mm": 0.127,
        "min_space_mm": 0.127,
        "min_via_drill_mm": 0.3,
        "min_via_pad_mm": 0.6,
        "min_hole_mm": 0.3,
        "board_thickness_mm": 1.6,
        "copper_oz": 1,
        "solder_mask": "green",
        "surface_finish": "HASL",
    },
    "jlcpcb_4layer": {
        "name": "JLCPCB 4-Layer",
        "layers": 4,
        "min_trace_mm": 0.09,
        "min_space_mm": 0.09,
        "min_via_drill_mm": 0.2,
        "min_via_pad_mm": 0.45,
        "min_hole_mm": 0.2,
        "board_thickness_mm": 1.6,
        "copper_oz": 1,
        "solder_mask": "green",
        "surface_finish": "ENIG",
        "impedance_control": True,
        "stackup": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"],
    },
    "pcbway": {
        "name": "PCBWay Standard",
        "layers": 2,
        "min_trace_mm": 0.1,
        "min_space_mm": 0.1,
        "min_via_drill_mm": 0.2,
        "min_via_pad_mm": 0.5,
        "min_hole_mm": 0.2,
        "board_thickness_mm": 1.6,
        "copper_oz": 1,
        "solder_mask": "green",
        "surface_finish": "HASL",
    },
}

ACTIONS = ["upload_design", "check_status", "export_gerber", "order_pcb", "get_rules"]


class PCBDesignerProvider(LLMProvider):
    """Provider REST pour le service PCB Designer AI.

    Le message utilisateur doit etre un JSON avec un champ ``action``.

    Exemple::

        provider = PCBDesignerProvider()
        response = await provider.send([{
            "role": "user",
            "content": json.dumps({
                "action": "upload_design",
                "file_path": "/tmp/board.kicad_pcb",
                "rules_preset": "jlcpcb_2layer",
            })
        }])
    """

    name = "pcbdesigner"
    default_model = "pcbdesigner-v1"
    cost_per_million = (0.0, 0.0)
    speed_rank = 6
    quality_rank = 7

    def __init__(self, api_url: str | None = None, timeout: float = 60.0):
        self.api_url = (api_url or os.environ.get("PCBDESIGNER_API_URL", "")).rstrip("/")
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
                content=json.dumps(
                    {"error": "Expected JSON with 'action' field", "supported_actions": ACTIONS}
                ),
                model=self.default_model,
                provider=self.name,
            )

        action = request.get("action", "")
        handler = {
            "upload_design": self._upload_design,
            "check_status": self._check_status,
            "export_gerber": self._export_gerber,
            "order_pcb": self._order_pcb,
            "get_rules": self._get_rules,
        }.get(action)

        if handler is None:
            result = {"error": f"Unknown action: {action}", "supported_actions": ACTIONS}
        else:
            try:
                result = await handler(request)
            except httpx.HTTPStatusError as exc:
                logger.exception("PCBDesigner API error")
                result = {"error": str(exc), "status_code": exc.response.status_code}
            except Exception as exc:
                logger.exception("PCBDesigner action failed")
                result = {"error": str(exc)}

        return LLMResponse(
            content=json.dumps(result, default=str),
            model=model or self.default_model,
            provider=self.name,
        )

    # -- actions -------------------------------------------------------------

    async def _upload_design(self, request: dict) -> dict:
        file_path = request.get("file_path")
        if not file_path:
            return {"error": "file_path required"}

        rules_preset = request.get("rules_preset", "jlcpcb_2layer")
        rules = DESIGN_RULES.get(rules_preset, DESIGN_RULES["jlcpcb_2layer"])

        payload = {
            "file_path": file_path,
            "rules": rules,
            "options": request.get("options", {}),
        }
        return await self._post("/v1/designs", payload)

    async def _check_status(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}
        return await self._get(f"/v1/designs/{job_id}/status")

    async def _export_gerber(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}

        payload = {
            "format": request.get("format", "gerber_x2"),
            "layers": request.get("layers"),
            "include_drill": request.get("include_drill", True),
        }
        return await self._post(f"/v1/designs/{job_id}/export/gerber", payload)

    async def _order_pcb(self, request: dict) -> dict:
        job_id = request.get("job_id")
        if not job_id:
            return {"error": "job_id required"}

        payload = {
            "manufacturer": request.get("manufacturer", "jlcpcb"),
            "quantity": request.get("quantity", 5),
            "options": request.get("options", {}),
        }
        return await self._post(f"/v1/designs/{job_id}/order", payload)

    async def _get_rules(self, request: dict) -> dict:
        preset = request.get("preset")
        if preset:
            rules = DESIGN_RULES.get(preset)
            if rules is None:
                return {"error": f"Unknown preset: {preset}", "available": list(DESIGN_RULES)}
            return {"preset": preset, "rules": rules}
        return {"presets": DESIGN_RULES}

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
        response = await self.send(
            messages, model=model, system=system, temperature=temperature, max_tokens=max_tokens
        )
        yield response.content

    def available_models(self) -> list[str]:
        return ["pcbdesigner-v1"]
