"""Altium Bridge — import/export utilities for Altium <-> KiCad BOM and netlist formats.

This is a utility module (not a full provider). It converts between:
  - Altium ASCII schematic BOM CSV  <->  KiCad BOM CSV
  - KiCad netlist (.net)            ->   Altium-compatible netlist

Functions:
    parse_altium_bom()              — parse an Altium BOM CSV into structured records
    convert_altium_to_kicad_bom()   — convert Altium BOM CSV to KiCad BOM CSV
    convert_kicad_to_altium_bom()   — convert KiCad BOM CSV to Altium BOM CSV
    parse_altium_schematic_ascii()  — parse Altium ASCII schematic export (.SchDoc text)
    convert_kicad_netlist_to_altium() — convert KiCad .net XML to Altium-compatible netlist
"""

from __future__ import annotations

import csv
import io
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

logger = logging.getLogger("mascarade.providers.altium_bridge")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BOMRecord:
    """Unified BOM record used as intermediate representation."""

    designator: str
    quantity: int = 1
    value: str = ""
    footprint: str = ""
    description: str = ""
    manufacturer: str = ""
    manufacturer_pn: str = ""
    supplier: str = ""
    supplier_pn: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class SchematicComponent:
    """Component parsed from Altium ASCII schematic export."""

    designator: str
    lib_ref: str = ""
    value: str = ""
    footprint: str = ""
    description: str = ""
    location_x: float = 0.0
    location_y: float = 0.0
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class NetlistNet:
    """A single net from a netlist."""

    name: str
    code: int = 0
    pins: list[tuple[str, str]] = field(default_factory=list)  # (component_ref, pin)


# ---------------------------------------------------------------------------
# Altium BOM column mappings
# ---------------------------------------------------------------------------

# Altium BOM exports vary, but these are the most common column headers.
ALTIUM_TO_UNIFIED: dict[str, str] = {
    "Designator": "designator",
    "Comment": "value",
    "Description": "description",
    "Footprint": "footprint",
    "Quantity": "quantity",
    "Manufacturer": "manufacturer",
    "Manufacturer Part Number": "manufacturer_pn",
    "Manufacturer Part Number 1": "manufacturer_pn",
    "Supplier": "supplier",
    "Supplier Part Number": "supplier_pn",
    "Supplier Part Number 1": "supplier_pn",
    # Variants
    "Value": "value",
    "Part Number": "manufacturer_pn",
    "MPN": "manufacturer_pn",
    "Mfr": "manufacturer",
}

KICAD_TO_UNIFIED: dict[str, str] = {
    "Reference": "designator",
    "Ref": "designator",
    "Value": "value",
    "Footprint": "footprint",
    "Datasheet": "description",
    "Description": "description",
    "Quantity": "quantity",
    "Qty": "quantity",
    "MPN": "manufacturer_pn",
    "Manufacturer": "manufacturer",
}


# ---------------------------------------------------------------------------
# BOM parsing — Altium
# ---------------------------------------------------------------------------


def parse_altium_bom(csv_content: str) -> list[BOMRecord]:
    """Parse an Altium BOM CSV string into a list of BOMRecord.

    Handles common Altium BOM export formats with flexible column matching.
    Designators like "R1, R2, R3" are kept grouped (not exploded).

    Args:
        csv_content: Raw CSV text from Altium BOM export.

    Returns:
        List of BOMRecord with fields populated from the CSV.
    """
    records: list[BOMRecord] = []
    reader = csv.DictReader(io.StringIO(csv_content))

    if reader.fieldnames is None:
        logger.warning("Empty or invalid Altium BOM CSV — no header row found")
        return records

    # Build column mapping for this specific file
    col_map: dict[str, str] = {}
    for col in reader.fieldnames:
        normalized = col.strip()
        if normalized in ALTIUM_TO_UNIFIED:
            col_map[col] = ALTIUM_TO_UNIFIED[normalized]

    for row in reader:
        designator = ""
        value = ""
        footprint = ""
        description = ""
        manufacturer = ""
        manufacturer_pn = ""
        supplier = ""
        supplier_pn = ""
        quantity = 1
        extra: dict[str, str] = {}

        for csv_col, unified_field in col_map.items():
            cell = (row.get(csv_col) or "").strip()
            if not cell:
                continue
            if unified_field == "designator":
                designator = cell
            elif unified_field == "value":
                value = cell
            elif unified_field == "footprint":
                footprint = cell
            elif unified_field == "description":
                description = cell
            elif unified_field == "manufacturer":
                manufacturer = cell
            elif unified_field == "manufacturer_pn":
                manufacturer_pn = cell
            elif unified_field == "supplier":
                supplier = cell
            elif unified_field == "supplier_pn":
                supplier_pn = cell
            elif unified_field == "quantity":
                try:
                    quantity = int(cell)
                except ValueError:
                    quantity = 1

        # Capture unmapped columns as extra
        for csv_col in row:
            if csv_col not in col_map and row[csv_col]:
                extra[csv_col.strip()] = row[csv_col].strip()

        if designator:
            records.append(BOMRecord(
                designator=designator,
                quantity=quantity,
                value=value,
                footprint=footprint,
                description=description,
                manufacturer=manufacturer,
                manufacturer_pn=manufacturer_pn,
                supplier=supplier,
                supplier_pn=supplier_pn,
                extra=extra,
            ))

    logger.info("Parsed %d BOM records from Altium CSV", len(records))
    return records


# ---------------------------------------------------------------------------
# BOM parsing — KiCad
# ---------------------------------------------------------------------------


def parse_kicad_bom(csv_content: str) -> list[BOMRecord]:
    """Parse a KiCad BOM CSV string into a list of BOMRecord.

    Args:
        csv_content: Raw CSV text from KiCad BOM export.

    Returns:
        List of BOMRecord.
    """
    records: list[BOMRecord] = []
    # KiCad BOMs sometimes have comment lines starting with #
    lines = [ln for ln in csv_content.splitlines() if not ln.startswith("#")]
    cleaned = "\n".join(lines)

    reader = csv.DictReader(io.StringIO(cleaned))
    if reader.fieldnames is None:
        logger.warning("Empty or invalid KiCad BOM CSV")
        return records

    col_map: dict[str, str] = {}
    for col in reader.fieldnames:
        normalized = col.strip()
        if normalized in KICAD_TO_UNIFIED:
            col_map[col] = KICAD_TO_UNIFIED[normalized]

    for row in reader:
        designator = ""
        value = ""
        footprint = ""
        description = ""
        manufacturer = ""
        manufacturer_pn = ""
        quantity = 1
        extra: dict[str, str] = {}

        for csv_col, unified_field in col_map.items():
            cell = (row.get(csv_col) or "").strip()
            if not cell:
                continue
            if unified_field == "designator":
                designator = cell
            elif unified_field == "value":
                value = cell
            elif unified_field == "footprint":
                footprint = cell
            elif unified_field == "description":
                description = cell
            elif unified_field == "manufacturer":
                manufacturer = cell
            elif unified_field == "manufacturer_pn":
                manufacturer_pn = cell
            elif unified_field == "quantity":
                try:
                    quantity = int(cell)
                except ValueError:
                    quantity = 1

        for csv_col in row:
            if csv_col not in col_map and row[csv_col]:
                extra[csv_col.strip()] = row[csv_col].strip()

        if designator:
            records.append(BOMRecord(
                designator=designator,
                quantity=quantity,
                value=value,
                footprint=footprint,
                description=description,
                manufacturer=manufacturer,
                manufacturer_pn=manufacturer_pn,
                extra=extra,
            ))

    logger.info("Parsed %d BOM records from KiCad CSV", len(records))
    return records


# ---------------------------------------------------------------------------
# BOM conversion — Altium -> KiCad
# ---------------------------------------------------------------------------


def convert_altium_to_kicad_bom(altium_csv: str) -> str:
    """Convert an Altium BOM CSV to KiCad BOM CSV format.

    Args:
        altium_csv: Raw CSV from Altium BOM export.

    Returns:
        CSV string in KiCad BOM format.
    """
    records = parse_altium_bom(altium_csv)
    return _records_to_kicad_csv(records)


def _records_to_kicad_csv(records: list[BOMRecord]) -> str:
    """Serialize BOMRecords to KiCad-style BOM CSV."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # KiCad BOM header
    writer.writerow([
        "Reference",
        "Value",
        "Footprint",
        "Description",
        "Quantity",
        "Manufacturer",
        "MPN",
    ])

    for rec in records:
        writer.writerow([
            rec.designator,
            rec.value,
            rec.footprint,
            rec.description,
            rec.quantity,
            rec.manufacturer,
            rec.manufacturer_pn,
        ])

    return output.getvalue()


# ---------------------------------------------------------------------------
# BOM conversion — KiCad -> Altium
# ---------------------------------------------------------------------------


def convert_kicad_to_altium_bom(kicad_csv: str) -> str:
    """Convert a KiCad BOM CSV to Altium-compatible BOM CSV format.

    Args:
        kicad_csv: Raw CSV from KiCad BOM export.

    Returns:
        CSV string in Altium-compatible BOM format.
    """
    records = parse_kicad_bom(kicad_csv)
    return _records_to_altium_csv(records)


def _records_to_altium_csv(records: list[BOMRecord]) -> str:
    """Serialize BOMRecords to Altium-style BOM CSV."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Altium BOM header (common export format)
    writer.writerow([
        "Designator",
        "Comment",
        "Footprint",
        "Description",
        "Quantity",
        "Manufacturer",
        "Manufacturer Part Number",
        "Supplier",
        "Supplier Part Number",
    ])

    for rec in records:
        writer.writerow([
            rec.designator,
            rec.value,
            rec.footprint,
            rec.description,
            rec.quantity,
            rec.manufacturer,
            rec.manufacturer_pn,
            rec.supplier,
            rec.supplier_pn,
        ])

    return output.getvalue()


# ---------------------------------------------------------------------------
# Altium ASCII schematic parser
# ---------------------------------------------------------------------------

# Altium ASCII .SchDoc text export uses a record-based format with
# pipe-delimited key=value pairs. This parser handles the common subset.

_RECORD_RE = re.compile(r"RECORD=(\d+)")
_FIELD_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)=([^|]*)")


def parse_altium_schematic_ascii(content: str) -> list[SchematicComponent]:
    """Parse an Altium ASCII schematic text export.

    Altium Designer can export schematics as ASCII text where each component
    appears as a block of pipe-delimited fields. This parser extracts
    component records (RECORD=1) and their parameters.

    Args:
        content: Full text of an Altium ASCII schematic export.

    Returns:
        List of SchematicComponent.
    """
    components: list[SchematicComponent] = []

    # Split on record boundaries — Altium uses pipe-delimited blocks
    # or newline-separated records depending on export version.
    # We handle both by splitting on lines and looking for RECORD= markers.
    blocks: list[str] = []
    current_block: list[str] = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            if current_block:
                blocks.append(" ".join(current_block))
                current_block = []
            continue
        # Some exports use | as field separator within a single line
        if "|RECORD=" in line and current_block:
            blocks.append(" ".join(current_block))
            current_block = [line]
        elif line.startswith("RECORD=") and current_block:
            blocks.append(" ".join(current_block))
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        blocks.append(" ".join(current_block))

    for block in blocks:
        fields = _parse_altium_fields(block)
        record_type = fields.get("RECORD", "")

        # RECORD=1 is a component in Altium schematic format
        if record_type != "1":
            continue

        comp = SchematicComponent(
            designator=fields.get("DESIGNATORID", fields.get("Designator", "")),
            lib_ref=fields.get("LIBREFERENCE", fields.get("LibReference", "")),
            value=fields.get("COMMENT", fields.get("Comment", fields.get("VALUE", ""))),
            footprint=fields.get("FOOTPRINT", fields.get("Footprint", "")),
            description=fields.get("COMPONENTDESCRIPTION", fields.get("Description", "")),
        )

        # Location
        try:
            comp.location_x = float(fields.get("LOCATION.X", "0"))
        except ValueError:
            pass
        try:
            comp.location_y = float(fields.get("LOCATION.Y", "0"))
        except ValueError:
            pass

        # Store all fields as parameters for downstream use
        comp.parameters = {
            k: v for k, v in fields.items()
            if k not in ("RECORD", "DESIGNATORID", "Designator",
                         "LIBREFERENCE", "LibReference", "COMMENT", "Comment",
                         "VALUE", "FOOTPRINT", "Footprint",
                         "COMPONENTDESCRIPTION", "Description",
                         "LOCATION.X", "LOCATION.Y")
        }

        if comp.designator or comp.lib_ref:
            components.append(comp)

    logger.info(
        "Parsed %d components from Altium ASCII schematic", len(components)
    )
    return components


def _parse_altium_fields(block: str) -> dict[str, str]:
    """Extract key=value fields from an Altium record block.

    Handles both pipe-delimited and space-separated formats.
    """
    fields: dict[str, str] = {}
    # Try pipe-delimited first
    if "|" in block:
        segments = block.split("|")
        for seg in segments:
            seg = seg.strip()
            match = _FIELD_RE.match(seg)
            if match:
                fields[match.group(1)] = match.group(2).strip()
    else:
        # Space or newline separated key=value pairs
        for match in _FIELD_RE.finditer(block):
            fields[match.group(1)] = match.group(2).strip()
    return fields


# ---------------------------------------------------------------------------
# Netlist conversion — KiCad .net XML -> Altium-compatible
# ---------------------------------------------------------------------------


def convert_kicad_netlist_to_altium(kicad_net_xml: str) -> str:
    """Convert a KiCad .net XML netlist to Altium-compatible text netlist.

    KiCad netlists are XML files with <nets><net> elements. Altium can import
    a simple text netlist format (Protel/Altium .NET format):

        [netname]
        component-pin
        component-pin

    Args:
        kicad_net_xml: Full XML content of a KiCad .net file.

    Returns:
        Text netlist string in Altium/Protel format.
    """
    nets = _parse_kicad_netlist_xml(kicad_net_xml)
    return _nets_to_altium_format(nets)


def _parse_kicad_netlist_xml(xml_content: str) -> list[NetlistNet]:
    """Parse KiCad .net XML into NetlistNet records."""
    nets: list[NetlistNet] = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        logger.error("Failed to parse KiCad netlist XML: %s", exc)
        return nets

    # KiCad netlist structure: <export><nets><net code="1" name="GND">
    nets_elem = root.find("nets")
    if nets_elem is None:
        # Try alternate structure
        nets_elem = root.find(".//nets")

    if nets_elem is None:
        logger.warning("No <nets> element found in KiCad netlist")
        return nets

    for net_elem in nets_elem.findall("net"):
        name = net_elem.get("name", "")
        code = int(net_elem.get("code", "0"))

        pins: list[tuple[str, str]] = []
        for node in net_elem.findall("node"):
            ref = node.get("ref", "")
            pin = node.get("pin", "")
            if ref and pin:
                pins.append((ref, pin))

        if name and pins:
            nets.append(NetlistNet(name=name, code=code, pins=pins))

    logger.info("Parsed %d nets from KiCad netlist XML", len(nets))
    return nets


def _nets_to_altium_format(nets: list[NetlistNet]) -> str:
    """Serialize nets to Altium/Protel text netlist format.

    Format:
        (
        NetName
        Component-Pin
        Component-Pin
        )
    """
    lines: list[str] = []

    for net in sorted(nets, key=lambda n: n.code):
        lines.append("(")
        lines.append(f"  {net.name}")
        for ref, pin in sorted(net.pins):
            lines.append(f"  {ref}-{pin}")
        lines.append(")")

    return "\n".join(lines) + "\n"
