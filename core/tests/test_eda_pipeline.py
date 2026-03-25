"""Tests for EDA pipeline and routing rules."""

import pytest
from mascarade.router.eda_pipeline import EDAPipeline, PipelineStep, PipelineResult
from mascarade.router.eda_routing_rules import recommend_provider


class TestPipelineSteps:
    @pytest.mark.asyncio
    async def test_full_pipeline_no_providers(self):
        pipeline = EDAPipeline()
        result = await pipeline.run("/tmp/test.kicad_sch")
        assert result.status in ("done", "partial")
        assert len(result.steps) == 4

    @pytest.mark.asyncio
    async def test_analyze_only(self):
        pipeline = EDAPipeline()
        result = await pipeline.run("/tmp/test.kicad_sch", steps=[PipelineStep.ANALYZE])
        assert len(result.steps) == 1
        assert result.steps[0].step == PipelineStep.ANALYZE
        assert result.steps[0].status == "done"

    @pytest.mark.asyncio
    async def test_bom_only(self):
        pipeline = EDAPipeline()
        result = await pipeline.run("/tmp/test.kicad_sch", steps=[PipelineStep.BOM])
        assert result.steps[0].status == "done"

    @pytest.mark.asyncio
    async def test_summary(self):
        pipeline = EDAPipeline()
        result = await pipeline.run("/tmp/test.kicad_sch", steps=[PipelineStep.ANALYZE])
        s = result.summary
        assert s["status"] in ("done", "partial", "failed")
        assert "steps" in s
        assert "data" in s


class TestRoutingRules:
    def test_simple_board(self):
        r = recommend_provider(layer_count=2, component_count=20)
        assert r["complexity"] == "simple"
        assert any(rec["provider"] == "kicad_router" for rec in r["recommendations"])

    def test_complex_board(self):
        r = recommend_provider(layer_count=6, component_count=300)
        assert r["complexity"] == "complex"
        assert any(rec["provider"] == "quilter" for rec in r["recommendations"])

    def test_moderate_board(self):
        r = recommend_provider(layer_count=4, component_count=80)
        assert r["complexity"] == "moderate"

    def test_fast_budget(self):
        r = recommend_provider(budget="fast")
        assert any(rec["provider"] == "pcbdesigner" for rec in r["recommendations"])

    def test_always_kicad_happy_for_analysis(self):
        r = recommend_provider()
        analysis = [rec for rec in r["recommendations"] if rec["step"] == "analyze"]
        assert len(analysis) == 1
        assert analysis[0]["provider"] == "kicad_happy"
