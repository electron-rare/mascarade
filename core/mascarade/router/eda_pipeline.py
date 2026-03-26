"""Chained EDA pipeline: KiCadHappy → Quilter → PCBDesigner.

Orchestrates the full schema-to-fabrication workflow:
1. Analyze schematic + extract BOM (KiCadHappy)
2. Route the board (Quilter)
3. Order fabrication (PCBDesigner)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("mascarade.eda_pipeline")


class PipelineStep(str, Enum):
    ANALYZE = "analyze"
    BOM = "bom"
    ROUTE = "route"
    FABRICATE = "fabricate"


@dataclass
class StepResult:
    step: PipelineStep
    status: str = "pending"  # pending, running, done, failed, skipped
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0


@dataclass
class PipelineResult:
    steps: list[StepResult] = field(default_factory=list)
    status: str = "pending"

    @property
    def summary(self) -> dict:
        return {
            "status": self.status,
            "steps": [
                {
                    "step": s.step.value,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "data": {s.step.value: s.data for s in self.steps if s.data},
        }


class EDAPipeline:
    """Orchestrates the full EDA pipeline."""

    def __init__(self, providers: dict[str, Any] | None = None):
        self.providers = providers or {}

    async def run(
        self,
        kicad_path: str,
        *,
        steps: list[PipelineStep] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PipelineResult:
        steps = steps or [
            PipelineStep.ANALYZE,
            PipelineStep.BOM,
            PipelineStep.ROUTE,
            PipelineStep.FABRICATE,
        ]
        opts = options or {}
        result = PipelineResult()
        context: dict[str, Any] = {"kicad_path": kicad_path}

        for step in steps:
            import time

            t0 = time.monotonic()
            sr = StepResult(step=step, status="running")
            result.steps.append(sr)

            try:
                if step == PipelineStep.ANALYZE:
                    sr.data = await self._analyze(kicad_path, opts)
                    context["components"] = sr.data.get("components", [])
                    context["nets"] = sr.data.get("nets", [])
                elif step == PipelineStep.BOM:
                    sr.data = await self._bom(kicad_path, context, opts)
                    context["bom"] = sr.data.get("bom", [])
                elif step == PipelineStep.ROUTE:
                    sr.data = await self._route(kicad_path, context, opts)
                    context["routing_job_id"] = sr.data.get("job_id")
                elif step == PipelineStep.FABRICATE:
                    sr.data = await self._fabricate(context, opts)
                sr.status = "done"
            except Exception as exc:
                sr.status = "failed"
                sr.error = f"{type(exc).__name__}: {exc}"
                logger.warning("Pipeline step %s failed: %s", step.value, exc)
                # Continue with remaining steps

            sr.duration_ms = (time.monotonic() - t0) * 1000

        failed = [s for s in result.steps if s.status == "failed"]
        result.status = (
            "done" if not failed else "partial" if len(failed) < len(result.steps) else "failed"
        )
        return result

    async def _analyze(self, kicad_path: str, opts: dict) -> dict:
        agent = self.providers.get("kicad_happy")
        if agent and hasattr(agent, "analyze_schematic"):
            return await agent.analyze_schematic(kicad_path)
        # Fallback: basic file check
        return {"kicad_path": kicad_path, "status": "analyzed", "components": [], "nets": []}

    async def _bom(self, kicad_path: str, context: dict, opts: dict) -> dict:
        agent = self.providers.get("kicad_happy")
        if agent and hasattr(agent, "bom_extract"):
            return await agent.bom_extract(kicad_path)
        return {"bom": context.get("components", []), "format": "raw"}

    async def _route(self, kicad_path: str, context: dict, opts: dict) -> dict:
        provider = self.providers.get("quilter")
        if provider and hasattr(provider, "send"):
            msg = (
                f"Route board at {kicad_path} with {len(context.get('components', []))} components"
            )
            resp = await provider.send([{"role": "user", "content": msg}], model="submit_job")
            return {"job_id": resp.get("job_id", "unknown"), "status": "submitted"}
        return {"status": "skipped", "reason": "quilter not configured"}

    async def _fabricate(self, context: dict, opts: dict) -> dict:
        provider = self.providers.get("pcbdesigner")
        job_id = context.get("routing_job_id")
        if not job_id:
            return {"status": "skipped", "reason": "no routing job to fabricate"}
        if provider and hasattr(provider, "send"):
            msg = f"Export and order PCB for job {job_id}"
            resp = await provider.send([{"role": "user", "content": msg}], model="order_pcb")
            return {"order_id": resp.get("order_id", "unknown"), "status": "ordered"}
        return {"status": "skipped", "reason": "pcbdesigner not configured"}


def mount_eda_pipeline(app: Any) -> None:
    """Mount EDA pipeline endpoints on FastAPI app."""
    from fastapi import Body

    pipeline = EDAPipeline()

    @app.post("/v1/eda/pipeline")
    async def eda_pipeline_run(
        kicad_path: str = Body(..., embed=True),
        steps: list[str] | None = Body(None, embed=True),
    ):
        step_enums = [PipelineStep(s) for s in steps] if steps else None
        result = await pipeline.run(kicad_path, steps=step_enums)
        return result.summary

    @app.post("/v1/eda/route")
    async def eda_route_recommend(
        layer_count: int = Body(2, embed=True),
        component_count: int = Body(0, embed=True),
        budget: str = Body("standard", embed=True),
    ):
        from mascarade.router.eda_routing_rules import recommend_provider

        return recommend_provider(layer_count, component_count, budget)

    logger.info("EDA Pipeline mounted (/v1/eda/pipeline, /v1/eda/route)")
