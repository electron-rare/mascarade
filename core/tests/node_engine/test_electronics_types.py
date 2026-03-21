"""Tests pour les types de domaine electronics."""

from mascarade.node_engine.domains.electronics.types import (
    COMPONENT_SPEC_TYPE,
    DRC_REPORT_TYPE,
    ELECTRONICS_DOMAIN_TYPES,
    FIRMWARE_BINARY_TYPE,
    NETLIST_TYPE,
    SCHEMATIC_TYPE,
    WAVEFORM_TYPE,
)


def test_electronics_domain_types_list():
    """La liste ELECTRONICS_DOMAIN_TYPES contient tous les types."""
    assert len(ELECTRONICS_DOMAIN_TYPES) == 6
    type_names = [dt.name for dt in ELECTRONICS_DOMAIN_TYPES]
    assert "Netlist" in type_names
    assert "Schematic" in type_names
    assert "Waveform" in type_names
    assert "FirmwareBinary" in type_names
    assert "ComponentSpec" in type_names
    assert "DRCReport" in type_names


def test_netlist_type_full_name():
    """Le type Netlist a le bon nom complet."""
    assert NETLIST_TYPE.full_name == "electronics.Netlist"
    assert NETLIST_TYPE.domain == "electronics"
    assert NETLIST_TYPE.name == "Netlist"


def test_netlist_type_validate_valid_spice():
    """Validation réussie pour un netlist SPICE valide."""
    data = {
        "format": "spice",
        "content": "* SPICE netlist\nV1 1 0 DC 5\nR1 1 0 1k\n.end",
        "components": ["V1", "R1"],
        "analyses": ["op"],
    }
    valid, error = NETLIST_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_netlist_type_validate_valid_kicad():
    """Validation réussie pour un netlist KiCad valide."""
    data = {
        "format": "kicad",
        "content": "(export (version D)\n  (components))",
    }
    valid, error = NETLIST_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_netlist_type_validate_missing_required():
    """Validation échoue si format ou content manque."""
    data = {"format": "spice"}
    valid, error = NETLIST_TYPE.validate_schema(data)
    assert valid is False
    assert "content" in error


def test_netlist_type_validate_invalid_format():
    """Validation échoue si format n'est pas dans l'enum."""
    data = {
        "format": "ltspice",
        "content": "* netlist",
    }
    valid, error = NETLIST_TYPE.validate_schema(data)
    assert valid is False
    assert "enum" in error


def test_schematic_type_full_name():
    """Le type Schematic a le bon nom complet."""
    assert SCHEMATIC_TYPE.full_name == "electronics.Schematic"


def test_schematic_type_validate_valid():
    """Validation réussie pour un schematic valide."""
    data = {
        "format": "kicad",
        "content": "(kicad_sch (version 20211123))",
        "sheets": ["main", "power"],
    }
    valid, error = SCHEMATIC_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_schematic_type_validate_svg_format():
    """Validation réussie pour un schematic SVG."""
    data = {
        "format": "svg",
        "content": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
    }
    valid, error = SCHEMATIC_TYPE.validate_schema(data)
    assert valid is True


def test_schematic_type_validate_invalid_format():
    """Validation échoue si format invalide."""
    data = {
        "format": "eagle",
        "content": "schematic",
    }
    valid, error = SCHEMATIC_TYPE.validate_schema(data)
    assert valid is False
    assert "enum" in error


def test_waveform_type_full_name():
    """Le type Waveform a le bon nom complet."""
    assert WAVEFORM_TYPE.full_name == "electronics.Waveform"


def test_waveform_type_validate_valid_transient():
    """Validation réussie pour un waveform transient."""
    data = {
        "signals": {
            "v(out)": [0.0, 1.2, 2.4, 3.3],
            "i(r1)": [0.0, 0.001, 0.002, 0.003],
        },
        "time_axis": [0.0, 1e-6, 2e-6, 3e-6],
        "units": {"v(out)": "V", "i(r1)": "A"},
        "analysis_type": "transient",
    }
    valid, error = WAVEFORM_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_waveform_type_validate_valid_ac():
    """Validation réussie pour un waveform AC."""
    data = {
        "signals": {"gain": [0.0, -3.0, -6.0]},
        "analysis_type": "ac",
    }
    valid, error = WAVEFORM_TYPE.validate_schema(data)
    assert valid is True


def test_waveform_type_validate_missing_required():
    """Validation échoue si signals ou analysis_type manque."""
    data = {
        "time_axis": [0.0, 1.0],
    }
    valid, error = WAVEFORM_TYPE.validate_schema(data)
    assert valid is False
    assert "signals" in error or "analysis_type" in error


def test_waveform_type_validate_invalid_analysis_type():
    """Validation échoue si analysis_type invalide."""
    data = {
        "signals": {"v": [1.0]},
        "analysis_type": "fft",
    }
    valid, error = WAVEFORM_TYPE.validate_schema(data)
    assert valid is False
    assert "enum" in error


def test_firmware_binary_type_full_name():
    """Le type FirmwareBinary a le bon nom complet."""
    assert FIRMWARE_BINARY_TYPE.full_name == "electronics.FirmwareBinary"


def test_firmware_binary_type_validate_valid():
    """Validation réussie pour un firmware binaire valide."""
    data = {
        "binary": "AAECAwQFBgcICQ==",  # base64 encoded
        "target": "esp32",
        "framework": "esp-idf",
        "size_bytes": 245678,
        "sections": {
            "text": 150000,
            "data": 50000,
            "bss": 30000,
            "rodata": 15678,
        },
    }
    valid, error = FIRMWARE_BINARY_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_firmware_binary_type_validate_platformio():
    """Validation réussie pour un firmware PlatformIO."""
    data = {
        "binary": "base64data",
        "target": "esp32s3",
        "framework": "platformio",
        "size_bytes": 100000,
    }
    valid, error = FIRMWARE_BINARY_TYPE.validate_schema(data)
    assert valid is True


def test_firmware_binary_type_validate_missing_required():
    """Validation échoue si un champ requis manque."""
    data = {
        "binary": "data",
        "target": "esp32",
        "framework": "esp-idf",
    }
    valid, error = FIRMWARE_BINARY_TYPE.validate_schema(data)
    assert valid is False
    assert "size_bytes" in error


def test_firmware_binary_type_validate_invalid_framework():
    """Validation échoue si framework invalide."""
    data = {
        "binary": "data",
        "target": "esp32",
        "framework": "zephyr",
        "size_bytes": 100000,
    }
    valid, error = FIRMWARE_BINARY_TYPE.validate_schema(data)
    assert valid is False
    assert "enum" in error


def test_component_spec_type_full_name():
    """Le type ComponentSpec a le bon nom complet."""
    assert COMPONENT_SPEC_TYPE.full_name == "electronics.ComponentSpec"


def test_component_spec_type_validate_valid():
    """Validation réussie pour un ComponentSpec valide."""
    data = {
        "mpn": "STM32F103C8T6",
        "manufacturer": "STMicroelectronics",
        "category": "Microcontroller",
        "parameters": {
            "cores": 1,
            "frequency": "72MHz",
            "flash": "64KB",
            "ram": "20KB",
        },
        "footprint": "LQFP-48",
        "lcsc_part": "C8734",
        "datasheet_url": "https://www.st.com/resource/en/datasheet/stm32f103c8.pdf",
    }
    valid, error = COMPONENT_SPEC_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_component_spec_type_validate_minimal():
    """Validation réussie avec seulement les champs requis."""
    data = {
        "mpn": "NE555",
        "manufacturer": "Texas Instruments",
        "category": "Timer",
    }
    valid, error = COMPONENT_SPEC_TYPE.validate_schema(data)
    assert valid is True


def test_component_spec_type_validate_with_null_optionals():
    """Validation réussie avec champs optionnels à null."""
    data = {
        "mpn": "Generic Resistor",
        "manufacturer": "Generic",
        "category": "Resistor",
        "parameters": {"resistance": "10k", "tolerance": "1%"},
        "footprint": "0402",
        "lcsc_part": None,
        "datasheet_url": None,
    }
    valid, error = COMPONENT_SPEC_TYPE.validate_schema(data)
    assert valid is True


def test_component_spec_type_validate_missing_required():
    """Validation échoue si un champ requis manque."""
    data = {
        "mpn": "ESP32-WROOM-32",
        "manufacturer": "Espressif",
    }
    valid, error = COMPONENT_SPEC_TYPE.validate_schema(data)
    assert valid is False
    assert "category" in error


def test_drc_report_type_full_name():
    """Le type DRCReport a le bon nom complet."""
    assert DRC_REPORT_TYPE.full_name == "electronics.DRCReport"


def test_drc_report_type_validate_valid_passed():
    """Validation réussie pour un rapport DRC sans violations."""
    data = {
        "passed": True,
        "violations": [],
        "rules_checked": 15,
        "board_file": "project.kicad_pcb",
    }
    valid, error = DRC_REPORT_TYPE.validate_schema(data)
    assert valid is True
    assert error is None


def test_drc_report_type_validate_valid_with_violations():
    """Validation réussie pour un rapport DRC avec violations."""
    data = {
        "passed": False,
        "violations": [
            {
                "rule": "clearance",
                "severity": "error",
                "location": {"x": 100.5, "y": 50.2, "layer": "F.Cu"},
                "message": "Clearance violation: 0.1mm < 0.127mm minimum",
            },
            {
                "rule": "track_width",
                "severity": "warning",
                "location": {"x": 120.0, "y": 60.0, "layer": "B.Cu"},
                "message": "Track width 0.12mm < 0.127mm recommended",
            },
        ],
        "rules_checked": 15,
        "board_file": "project.kicad_pcb",
    }
    valid, error = DRC_REPORT_TYPE.validate_schema(data)
    assert valid is True


def test_drc_report_type_validate_missing_required():
    """Validation échoue si un champ requis manque."""
    data = {
        "passed": True,
        "violations": [],
        "rules_checked": 10,
    }
    valid, error = DRC_REPORT_TYPE.validate_schema(data)
    assert valid is False
    assert "board_file" in error


def test_all_types_have_electronics_domain():
    """Tous les types electronics ont le domaine 'electronics'."""
    for domain_type in ELECTRONICS_DOMAIN_TYPES:
        assert domain_type.domain == "electronics"


def test_all_types_have_object_schema():
    """Tous les types electronics ont un schéma de type object."""
    for domain_type in ELECTRONICS_DOMAIN_TYPES:
        assert domain_type.schema.get("type") == "object"


def test_all_types_have_required_fields():
    """Tous les types electronics ont des champs requis."""
    for domain_type in ELECTRONICS_DOMAIN_TYPES:
        required = domain_type.schema.get("required", [])
        assert len(required) > 0, f"{domain_type.name} should have required fields"
