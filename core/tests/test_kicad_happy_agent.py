"""Tests for KiCadHappyAgent — Plan 26 EDA Phase 2."""

from __future__ import annotations

import csv
import io
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.agents.kicad_happy_agent import (
    DFM_RULES,
    LCSC_COMPONENTS,
    DFMViolation,
    KiCadHappyAgent,
    SchComponent,
    SchNet,
    _bom_to_digikey_csv,
    _bom_to_jlcpcb_csv,
    _bom_to_mouser_csv,
    _lookup_component_info,
    _lookup_lcsc,
    _parse_sexpr,
    _tokenize_sexpr,
    dfm_check,
    parse_kicad_sch,
)

# ---------------------------------------------------------------------------
# Sample KiCad schematic (minimal S-expression)
# ---------------------------------------------------------------------------

SAMPLE_KICAD_SCH = textwrap.dedent("""\
    (kicad_sch (version 20211014) (generator eeschema)
      (lib_symbols)
      (symbol (lib_id "Device:R") (at 100.0 50.0 0)
        (property "Reference" "R1")
        (property "Value" "R_10K")
        (property "Footprint" "Resistor_SMD:R_0402_1005Metric")
      )
      (symbol (lib_id "Device:C") (at 120.0 50.0 0)
        (property "Reference" "C1")
        (property "Value" "C_100nF")
        (property "Footprint" "Capacitor_SMD:C_0402_1005Metric")
      )
      (symbol (lib_id "Connector:USB_C_Receptacle") (at 80.0 70.0 0)
        (property "Reference" "J1")
        (property "Value" "USB_C_16P")
        (property "Footprint" "Connector_USB:USB_C_Receptacle_XKB_U262-161N-4BVC11")
      )
      (label "VCC" (at 90.0 40.0 0))
      (label "GND" (at 90.0 80.0 0))
      (global_label "SDA" (at 140.0 50.0 0))
      (global_label "SCL" (at 140.0 55.0 0))
    )
""")


@pytest.fixture()
def sch_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.kicad_sch"
    p.write_text(SAMPLE_KICAD_SCH, encoding="utf-8")
    return p


@pytest.fixture()
def agent() -> KiCadHappyAgent:
    return KiCadHappyAgent()


# ---------------------------------------------------------------------------
# S-expression parser
# ---------------------------------------------------------------------------

class TestSExpressionParser:
    def test_tokenize_simple(self):
        tokens = _tokenize_sexpr('(hello "world" 42)')
        assert tokens == ["(", "hello", '"world"', "42", ")"]

    def test_tokenize_nested(self):
        tokens = _tokenize_sexpr('(a (b c))')
        assert tokens == ["(", "a", "(", "b", "c", ")", ")"]

    def test_parse_flat(self):
        tokens = _tokenize_sexpr("(foo bar 123)")
        tree, _ = _parse_sexpr(tokens)
        assert tree == [["foo", "bar", "123"]]

    def test_parse_nested(self):
        tokens = _tokenize_sexpr("(a (b c) d)")
        tree, _ = _parse_sexpr(tokens)
        assert tree == [["a", ["b", "c"], "d"]]

    def test_parse_quoted_string_stripped(self):
        tokens = _tokenize_sexpr('(property "Reference" "R1")')
        tree, _ = _parse_sexpr(tokens)
        assert tree == [["property", "Reference", "R1"]]

    def test_parse_kicad_sch_file(self, sch_file: Path):
        components, nets = parse_kicad_sch(sch_file)
        assert len(components) == 3
        refs = {c.reference for c in components}
        assert refs == {"R1", "C1", "J1"}

    def test_component_positions(self, sch_file: Path):
        components, _ = parse_kicad_sch(sch_file)
        r1 = next(c for c in components if c.reference == "R1")
        assert r1.position == (100.0, 50.0)

    def test_component_lib_id(self, sch_file: Path):
        components, _ = parse_kicad_sch(sch_file)
        c1 = next(c for c in components if c.reference == "C1")
        assert c1.lib_id == "Device:C"

    def test_net_labels(self, sch_file: Path):
        _, nets = parse_kicad_sch(sch_file)
        net_names = {n.name for n in nets}
        assert "VCC" in net_names
        assert "GND" in net_names
        assert "SDA" in net_names
        assert "SCL" in net_names


# ---------------------------------------------------------------------------
# BOM extraction
# ---------------------------------------------------------------------------

class TestBOMExtraction:
    @pytest.mark.asyncio
    async def test_bom_extract(self, agent, sch_file):
        bom = await agent.bom_extract(str(sch_file))
        assert len(bom) == 3
        refs = {b["reference"] for b in bom}
        assert refs == {"R1", "C1", "J1"}

    @pytest.mark.asyncio
    async def test_bom_extract_lcsc_present(self, agent, sch_file):
        bom = await agent.bom_extract(str(sch_file))
        r1 = next(b for b in bom if b["reference"] == "R1")
        # R_10K is in the LCSC database
        assert r1["lcsc"] == "C25744"

    @pytest.mark.asyncio
    async def test_bom_extract_values(self, agent, sch_file):
        bom = await agent.bom_extract(str(sch_file))
        c1 = next(b for b in bom if b["reference"] == "C1")
        assert c1["value"] == "C_100nF"
        assert "0402" in c1["footprint"]


# ---------------------------------------------------------------------------
# LCSC component sourcing
# ---------------------------------------------------------------------------

class TestComponentSourcing:
    def test_lookup_direct_match(self):
        info = _lookup_component_info("R_10K")
        assert info["lcsc"] == "C25744"
        assert info["mpn"] == "0402WGF1002TCE"

    def test_lookup_case_insensitive(self):
        info = _lookup_component_info("r_10k")
        assert info["lcsc"] == "C25744"

    def test_lookup_lcsc_shortcut(self):
        assert _lookup_lcsc("C_100nF") == "C1525"

    def test_lookup_unknown_returns_empty(self):
        info = _lookup_component_info("XYZ_FANTASY_PART")
        assert info == {}

    def test_lookup_lcsc_unknown_returns_empty_string(self):
        assert _lookup_lcsc("UNKNOWN") == ""

    @pytest.mark.asyncio
    async def test_component_source_search(self, agent):
        matches = await agent.component_source("ESP32")
        assert len(matches) >= 2
        keys = {m["key"] for m in matches}
        assert "ESP32_S3_WROOM" in keys
        assert "ESP32_C3_MINI" in keys

    @pytest.mark.asyncio
    async def test_component_source_resistor(self, agent):
        matches = await agent.component_source("0402WGF1001")
        assert len(matches) >= 1
        assert matches[0]["key"] == "R_1K"

    @pytest.mark.asyncio
    async def test_component_source_no_results(self, agent):
        matches = await agent.component_source("ZZZZNOTFOUND")
        assert matches == []


# ---------------------------------------------------------------------------
# BOM export formats
# ---------------------------------------------------------------------------

class TestBOMExport:
    @pytest.fixture()
    def sample_components(self) -> list[SchComponent]:
        return [
            SchComponent(reference="R1", value="R_10K", footprint="R_0402"),
            SchComponent(reference="C1", value="C_100nF", footprint="C_0402"),
        ]

    def test_jlcpcb_csv(self, sample_components):
        csv_str = _bom_to_jlcpcb_csv(sample_components)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        header = rows[0]
        assert header == ["Comment", "Designator", "Footprint", "LCSC Part #"]
        assert rows[1][0] == "R_10K"
        assert rows[1][1] == "R1"
        assert rows[1][3] == "C25744"  # known LCSC
        assert rows[2][3] == "C1525"   # C_100nF

    def test_digikey_csv(self, sample_components):
        csv_str = _bom_to_digikey_csv(sample_components)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        header = rows[0]
        assert header == ["Quantity", "Reference", "Value", "Footprint", "Description"]
        assert rows[1][1] == "R1"
        assert rows[1][2] == "R_10K"

    def test_mouser_csv(self, sample_components):
        csv_str = _bom_to_mouser_csv(sample_components)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        header = rows[0]
        assert header == ["Mouser Part Number", "Manufacturer Part Number", "Quantity", "Reference", "Description"]
        assert rows[1][1] == "0402WGF1002TCE"  # MPN for R_10K
        assert rows[1][3] == "R1"

    @pytest.mark.asyncio
    async def test_bom_export_jlcpcb(self, agent, sch_file):
        csv_str = await agent.bom_export(str(sch_file), fmt="jlcpcb")
        assert "LCSC Part #" in csv_str
        assert "R1" in csv_str

    @pytest.mark.asyncio
    async def test_bom_export_digikey(self, agent, sch_file):
        csv_str = await agent.bom_export(str(sch_file), fmt="digikey")
        assert "Quantity" in csv_str
        assert "Description" in csv_str

    @pytest.mark.asyncio
    async def test_bom_export_mouser(self, agent, sch_file):
        csv_str = await agent.bom_export(str(sch_file), fmt="mouser")
        assert "Mouser Part Number" in csv_str

    @pytest.mark.asyncio
    async def test_bom_export_unknown_format(self, agent, sch_file):
        result = await agent.bom_export(str(sch_file), fmt="arrow")
        assert "Unknown format" in result


# ---------------------------------------------------------------------------
# DFM check heuristics
# ---------------------------------------------------------------------------

class TestDFMCheck:
    def test_no_violations_on_good_design(self):
        violations = dfm_check(
            trace_widths_mm=[0.2, 0.3],
            via_drills_mm=[0.4, 0.5],
            clearances_mm=[0.2, 0.3],
            manufacturer="jlcpcb",
        )
        assert len(violations) == 0

    def test_trace_width_error(self):
        violations = dfm_check(trace_widths_mm=[0.05], manufacturer="jlcpcb")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 1
        assert errors[0].rule == "min_trace_width"
        assert "0.050mm" in errors[0].message

    def test_trace_width_warning(self):
        # 0.15 is above 0.127 but below 0.127*1.5=0.1905
        violations = dfm_check(trace_widths_mm=[0.15], manufacturer="jlcpcb")
        warnings = [v for v in violations if v.severity == "warning"]
        assert len(warnings) == 1
        assert warnings[0].rule == "trace_width_margin"

    def test_via_drill_error(self):
        violations = dfm_check(via_drills_mm=[0.1], manufacturer="jlcpcb")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 1
        assert errors[0].rule == "min_via_drill"

    def test_clearance_error(self):
        violations = dfm_check(clearances_mm=[0.05], manufacturer="jlcpcb")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 1
        assert errors[0].rule == "min_clearance"

    def test_via_annular_error(self):
        violations = dfm_check(via_annulars_mm=[0.05], manufacturer="jlcpcb")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 1
        assert errors[0].rule == "min_via_annular"

    def test_pcbway_more_lenient(self):
        # 0.11mm trace passes for pcbway (min 0.1) but fails for jlcpcb (min 0.127)
        violations_pcbway = dfm_check(trace_widths_mm=[0.11], manufacturer="pcbway")
        violations_jlcpcb = dfm_check(trace_widths_mm=[0.11], manufacturer="jlcpcb")
        pcbway_errors = [v for v in violations_pcbway if v.severity == "error"]
        jlcpcb_errors = [v for v in violations_jlcpcb if v.severity == "error"]
        assert len(pcbway_errors) == 0
        assert len(jlcpcb_errors) == 1

    def test_multiple_violations(self):
        violations = dfm_check(
            trace_widths_mm=[0.05, 0.06],
            via_drills_mm=[0.1],
            clearances_mm=[0.01],
            manufacturer="jlcpcb",
        )
        assert len(violations) >= 4

    def test_empty_inputs(self):
        violations = dfm_check(manufacturer="jlcpcb")
        assert violations == []

    def test_unknown_manufacturer_defaults_to_jlcpcb(self):
        violations = dfm_check(trace_widths_mm=[0.05], manufacturer="unknown_fab")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 1  # uses jlcpcb rules

    def test_violation_location_indexing(self):
        violations = dfm_check(trace_widths_mm=[0.5, 0.05, 0.5], manufacturer="jlcpcb")
        error = next(v for v in violations if v.severity == "error")
        assert error.location == "trace[1]"


# ---------------------------------------------------------------------------
# DFM check via agent skill
# ---------------------------------------------------------------------------

class TestDFMCheckSkill:
    @pytest.mark.asyncio
    async def test_dfm_check_skill_pass(self, agent):
        result = await agent.dfm_check_skill(
            trace_widths_mm=[0.2, 0.3],
            via_drills_mm=[0.4],
            manufacturer="jlcpcb",
        )
        assert result["pass"] is True
        assert result["errors"] == 0
        assert result["manufacturer"] == "jlcpcb"

    @pytest.mark.asyncio
    async def test_dfm_check_skill_fail(self, agent):
        result = await agent.dfm_check_skill(
            trace_widths_mm=[0.05],
            manufacturer="jlcpcb",
        )
        assert result["pass"] is False
        assert result["errors"] >= 1
        assert len(result["violations"]) >= 1
        v = result["violations"][0]
        assert "rule" in v
        assert "message" in v
        assert "severity" in v


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------

class TestAgentMetadata:
    def test_agent_name(self, agent):
        assert agent.name == "kicad-happy"

    def test_agent_category(self, agent):
        assert agent.category == "eda"

    def test_agent_skills_list(self, agent):
        assert "bom_extract" in agent.skills
        assert "dfm_check" in agent.skills
        assert "analyze_schematic" in agent.skills
        assert len(agent.skills) == 7

    def test_agent_tools(self, agent):
        assert "kicad_api" in agent.tools

    def test_agent_temperature(self, agent):
        assert agent.temperature == 0.2


# ---------------------------------------------------------------------------
# Analyze schematic
# ---------------------------------------------------------------------------

class TestAnalyzeSchematic:
    @pytest.mark.asyncio
    async def test_analyze_schematic(self, agent, sch_file):
        result = await agent.analyze_schematic(str(sch_file))
        assert result["component_count"] == 3
        assert result["unique_nets"] >= 2
        refs = {c["ref"] for c in result["components"]}
        assert refs == {"R1", "C1", "J1"}

    @pytest.mark.asyncio
    async def test_analyze_schematic_file_not_found(self, agent):
        result = await agent.analyze_schematic("/nonexistent/path.kicad_sch")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_schematic_net_labels(self, agent, sch_file):
        result = await agent.analyze_schematic(str(sch_file))
        assert "VCC" in result["net_labels"]
        assert "GND" in result["net_labels"]
