"""Tests for the CAD domain worker."""

import pytest

from mascarade.node_engine.workers.cad import CAD_DOMAIN_TYPES
from mascarade.node_engine.workers.cad.worker import CADWorker


class TestCADCapabilities:
    def setup_method(self):
        self.worker = CADWorker()

    def test_6_node_types(self):
        assert len(self.worker.capabilities()) == 6

    def test_match_domain_types(self):
        assert {c["node_type"] for c in self.worker.capabilities()} == set(
            CAD_DOMAIN_TYPES
        )


class TestBOMGenerate:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_basic_bom(self):
        r = await self.worker.execute(
            "cad.bom-generate",
            {
                "components": [
                    {"ref": "R1", "value": "10k", "footprint": "0805"},
                    {"ref": "R2", "value": "10k", "footprint": "0805"},
                    {"ref": "C1", "value": "100nF", "footprint": "0402"},
                ]
            },
            {},
        )
        assert r["total_unique"] == 2
        assert r["total_qty"] == 3

    @pytest.mark.asyncio
    async def test_empty_bom(self):
        r = await self.worker.execute("cad.bom-generate", {"components": []}, {})
        assert r["total_unique"] == 0

    def test_validate_missing_components(self):
        errors = self.worker.validate("cad.bom-generate", {}, {})
        assert len(errors) > 0


class TestDRCCheck:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_passing_drc(self):
        r = await self.worker.execute(
            "cad.drc-check",
            {
                "rules": {
                    "min_trace_width": 0.15,
                    "min_clearance": 0.15,
                    "min_drill": 0.3,
                },
                "design": {
                    "min_trace_width": 0.2,
                    "min_clearance": 0.2,
                    "min_drill": 0.4,
                },
            },
            {},
        )
        assert r["passed"] is True
        assert len(r["violations"]) == 0

    @pytest.mark.asyncio
    async def test_failing_drc(self):
        r = await self.worker.execute(
            "cad.drc-check",
            {
                "rules": {"min_trace_width": 0.15},
                "design": {"min_trace_width": 0.10},
            },
            {},
        )
        assert r["passed"] is False
        assert len(r["violations"]) > 0


class TestFootprintLookup:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_0805(self):
        r = await self.worker.execute("cad.footprint-lookup", {"package": "0805"}, {})
        assert r["pads"] == 2
        assert "0805" in r["footprint"]

    @pytest.mark.asyncio
    async def test_sot23(self):
        r = await self.worker.execute("cad.footprint-lookup", {"package": "SOT-23"}, {})
        assert r["pads"] == 3

    @pytest.mark.asyncio
    async def test_tqfp48(self):
        r = await self.worker.execute(
            "cad.footprint-lookup", {"package": "TQFP-48"}, {}
        )
        assert r["pads"] == 48

    @pytest.mark.asyncio
    async def test_unknown(self):
        r = await self.worker.execute(
            "cad.footprint-lookup", {"package": "WEIRD-99"}, {}
        )
        assert r["pads"] == 0
        assert "note" in r

    def test_validate_missing_package(self):
        errors = self.worker.validate("cad.footprint-lookup", {}, {})
        assert len(errors) > 0


class TestStackupCalc:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_4_layer(self):
        r = await self.worker.execute(
            "cad.stackup-calc", {"layers": 4, "thickness": 1.6}, {}
        )
        assert r["layers"] == 4
        assert len(r["stackup"]) == 7  # 4 copper + 3 dielectric
        assert r["stackup"][0]["name"] == "Top"
        assert r["stackup"][-1]["name"] == "Bottom"

    @pytest.mark.asyncio
    async def test_2_layer(self):
        r = await self.worker.execute("cad.stackup-calc", {"layers": 2}, {})
        assert r["layers"] == 2
        assert len(r["stackup"]) == 3  # 2 copper + 1 dielectric

    def test_validate_odd_layers(self):
        errors = self.worker.validate("cad.stackup-calc", {"layers": 3}, {})
        assert len(errors) > 0


class TestTraceWidth:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_1a_external(self):
        r = await self.worker.execute(
            "cad.trace-width",
            {
                "current": 1.0,
                "copper_thickness": 1.0,
                "temp_rise": 10,
                "layer": "external",
            },
            {},
        )
        assert r["width_mm"] > 0
        assert r["width_mil"] > 0

    @pytest.mark.asyncio
    async def test_3a_needs_wider(self):
        r1 = await self.worker.execute(
            "cad.trace-width", {"current": 1.0, "layer": "external"}, {}
        )
        r3 = await self.worker.execute(
            "cad.trace-width", {"current": 3.0, "layer": "external"}, {}
        )
        assert r3["width_mm"] > r1["width_mm"]

    @pytest.mark.asyncio
    async def test_internal_wider_than_external(self):
        re = await self.worker.execute(
            "cad.trace-width", {"current": 2.0, "layer": "external"}, {}
        )
        ri = await self.worker.execute(
            "cad.trace-width", {"current": 2.0, "layer": "internal"}, {}
        )
        assert ri["width_mm"] > re["width_mm"]  # Internal needs wider trace

    def test_validate_zero_current(self):
        errors = self.worker.validate("cad.trace-width", {"current": 0}, {})
        assert len(errors) > 0


class TestThermalVia:
    def setup_method(self):
        self.worker = CADWorker()

    @pytest.mark.asyncio
    async def test_basic_thermal(self):
        r = await self.worker.execute(
            "cad.thermal-via",
            {"power": 1.0, "via_diameter": 0.3, "board_thickness": 1.6},
            {},
        )
        assert r["vias_needed"] >= 1
        assert r["thermal_resistance_per_via"] > 0

    @pytest.mark.asyncio
    async def test_more_power_more_vias(self):
        r1 = await self.worker.execute("cad.thermal-via", {"power": 1.0}, {})
        r5 = await self.worker.execute("cad.thermal-via", {"power": 5.0}, {})
        assert r5["vias_needed"] >= r1["vias_needed"]

    def test_validate_no_power(self):
        errors = self.worker.validate("cad.thermal-via", {}, {})
        assert len(errors) > 0
