#!/usr/bin/env python3
"""Build fine-tuning dataset for KiCad/PCB routing domain.

Covers: KiCad (Eeschema, PCB Editor, footprints, Python scripting),
        PCB routing (impedance, stackup, DRC), IPC standards,
        Gerber generation, BOM, JLCPCB/PCBWay manufacturing.

Usage:
  python build_kicad_dataset.py                    # Seeds only (~15 examples)
  python build_kicad_dataset.py --with-hf          # Seeds + HuggingFace datasets
  python build_kicad_dataset.py --max-samples 2000 # Limit HF samples per source
"""

import argparse
import json
import os
import re

SYSTEM_PROMPT = (
    "You are an expert PCB design engineer and KiCad specialist. "
    "You master the full EDA workflow: schematic capture (Eeschema), "
    "footprint assignment, component placement, routing (manual and interactive), "
    "ground/power planes, vias, differential pairs, controlled impedance, "
    "design rule checks (DRC), Gerber/drill generation, and BOM for manufacturing. "
    "You know IPC standards (IPC-2221, IPC-A-610, IPC-J-STD-001, IPC-7351, IPC-2581). "
    "You provide practical answers with impedance calculations, stackup recommendations, "
    "EMC routing guidelines, thermal analysis, KiCad Python scripts, and DRC configurations. "
    "You know KiCad 8/9 file formats (.kicad_sch, .kicad_pcb, .kicad_mod)."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How do I calculate microstrip impedance for a 50Ω trace on a 4-layer PCB with FR4?",
            },
            {
                "from": "gpt",
                "value": """Microstrip impedance calculation for 50Ω on FR4:

**Formula (IPC-2141 / Wadell):**
```
Z₀ = (87 / √(εr + 1.41)) × ln(5.98 × h / (0.8 × w + t))
```

Where:
- εr = 4.4 (FR4 at 1GHz, use 4.2-4.6 depending on frequency)
- h = dielectric thickness (Layer 1 to Layer 2 ground plane)
- w = trace width
- t = copper thickness (typically 35µm = 1oz)

**Example: Standard 4-layer 1.6mm FR4 stackup:**
```
Layer 1: Signal (35µm Cu)
         Prepreg: 0.2mm (200µm) — εr = 4.4
Layer 2: GND plane (35µm Cu)
         Core: 1.0mm
Layer 3: Power plane (35µm Cu)
         Prepreg: 0.2mm
Layer 4: Signal (35µm Cu)
```

For 50Ω on outer layers (h = 0.2mm, t = 35µm):
```
50 = (87 / √(4.4 + 1.41)) × ln(5.98 × 0.2 / (0.8w + 0.035))
```

Solving: **w ≈ 0.34mm (13.4 mil)**

**In KiCad:** Edit → Board Setup → Design Rules → Net Classes:
- Set track width to 0.34mm for 50Ω nets
- Or use the built-in impedance calculator: Inspect → Board Statistics → Calculator

**Quick reference for FR4 1.6mm 4-layer:**
| Impedance | Trace Width | h=0.2mm |
|-----------|-------------|---------|
| 50Ω | 0.34mm | Single-ended |
| 75Ω | 0.17mm | Single-ended |
| 90Ω diff | 0.15mm / 0.2mm gap | Differential |
| 100Ω diff | 0.13mm / 0.2mm gap | Differential |

**Important:** Always get the actual stackup from your PCB manufacturer and use their impedance calculator for production designs. The formulas above are approximations.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a KiCad Python script to create a QFN-48 footprint with exposed pad.",
            },
            {
                "from": "gpt",
                "value": """KiCad Python script for QFN-48 (7×7mm, 0.5mm pitch) with exposed thermal pad:

```python
import pcbnew

def create_qfn48(board=None):
    \"\"\"Create QFN-48 footprint per IPC-7351 nominal land pattern.\"\"\"
    if board is None:
        board = pcbnew.GetBoard()

    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference("U1")
    fp.SetValue("QFN-48")

    # QFN-48 parameters (7x7mm body, 0.5mm pitch)
    BODY = 7.0          # mm body size
    PAD_COUNT = 48       # total pads
    PITCH = 0.5          # mm pad pitch
    PAD_W = 0.3          # mm pad width (IPC nominal)
    PAD_L = 0.8          # mm pad length (extension beyond body)
    EPAD_SIZE = 5.2      # mm exposed pad (thermal)

    pads_per_side = PAD_COUNT // 4  # 12 per side

    def mm_to_nm(mm):
        return int(mm * 1e6)

    # Create pads for each side
    pad_num = 1
    for side in range(4):
        for i in range(pads_per_side):
            pad = pcbnew.PAD(fp)
            pad.SetNumber(str(pad_num))
            pad.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
            pad.SetRoundRectRadiusRatio(0.25)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            pad.SetLayerSet(pcbnew.PAD(fp).SMDMask())

            # Calculate position
            offset = (i - (pads_per_side - 1) / 2) * PITCH
            center_dist = BODY / 2 + PAD_L / 2 - 0.1  # slight inset

            if side == 0:    # Bottom (pin 1 starts bottom-left)
                pad.SetPosition(pcbnew.VECTOR2I(mm_to_nm(offset), mm_to_nm(center_dist)))
                pad.SetSize(pcbnew.VECTOR2I(mm_to_nm(PAD_W), mm_to_nm(PAD_L)))
            elif side == 1:  # Right
                pad.SetPosition(pcbnew.VECTOR2I(mm_to_nm(center_dist), mm_to_nm(-offset)))
                pad.SetSize(pcbnew.VECTOR2I(mm_to_nm(PAD_L), mm_to_nm(PAD_W)))
            elif side == 2:  # Top
                pad.SetPosition(pcbnew.VECTOR2I(mm_to_nm(-offset), mm_to_nm(-center_dist)))
                pad.SetSize(pcbnew.VECTOR2I(mm_to_nm(PAD_W), mm_to_nm(PAD_L)))
            elif side == 3:  # Left
                pad.SetPosition(pcbnew.VECTOR2I(mm_to_nm(-center_dist), mm_to_nm(offset)))
                pad.SetSize(pcbnew.VECTOR2I(mm_to_nm(PAD_L), mm_to_nm(PAD_W)))

            fp.Add(pad)
            pad_num += 1

    # Exposed thermal pad (center)
    epad = pcbnew.PAD(fp)
    epad.SetNumber(str(pad_num))
    epad.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
    epad.SetRoundRectRadiusRatio(0.1)
    epad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    epad.SetSize(pcbnew.VECTOR2I(mm_to_nm(EPAD_SIZE), mm_to_nm(EPAD_SIZE)))
    epad.SetPosition(pcbnew.VECTOR2I(0, 0))

    # Thermal vias pattern in paste layer (3x3 grid)
    paste_mask = epad.GetLayerSet()
    epad.SetLayerSet(paste_mask)
    fp.Add(epad)

    # Courtyard (IPC-7351: 0.25mm beyond pads)
    courtyard_size = BODY / 2 + PAD_L + 0.25
    fp.GetLayer()  # Ensure layers are initialized

    # Silkscreen outline
    silk_offset = BODY / 2 + 0.1
    for layer in [pcbnew.F_SilkS]:
        # Draw body outline with pin 1 marker
        # Top line
        fp.Add(_line(fp, -silk_offset, -silk_offset, silk_offset, -silk_offset, layer))
        # Right line
        fp.Add(_line(fp, silk_offset, -silk_offset, silk_offset, silk_offset, layer))
        # Bottom line
        fp.Add(_line(fp, silk_offset, silk_offset, -silk_offset, silk_offset, layer))
        # Left line (with gap for pin 1)
        fp.Add(_line(fp, -silk_offset, silk_offset, -silk_offset, -silk_offset, layer))

    board.Add(fp)
    pcbnew.Refresh()
    return fp


def _line(fp, x1, y1, x2, y2, layer, width=0.12):
    \"\"\"Helper to create a line on a footprint.\"\"\"
    line = pcbnew.FP_SHAPE(fp)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(pcbnew.VECTOR2I(int(x1*1e6), int(y1*1e6)))
    line.SetEnd(pcbnew.VECTOR2I(int(x2*1e6), int(y2*1e6)))
    line.SetLayer(layer)
    line.SetWidth(int(width*1e6))
    return line
```

Run in KiCad Python console: `exec(open("create_qfn48.py").read())`

Key IPC-7351 guidelines for QFN:
- Pad extension beyond body: 0.4-0.8mm (nominal 0.65mm)
- Exposed pad: typically 60-80% of body size
- Thermal vias in exposed pad: 0.3mm drill, 0.6mm annular ring, 1mm pitch grid
- Solder paste: 50-80% coverage on exposed pad (avoid voids)""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "What is the recommended 4-layer PCB stackup for a mixed-signal design with USB 2.0?",
            },
            {
                "from": "gpt",
                "value": """Recommended 4-layer stackup for mixed-signal + USB 2.0:

```
Layer 1: Signal + USB (35µm Cu, 1oz)
         Prepreg: 0.2mm (7628) — εr ≈ 4.4
Layer 2: GND plane (35µm Cu, 1oz)
         Core: 1.0mm (FR4) — εr ≈ 4.5
Layer 3: Power plane + low-speed signals (35µm Cu, 1oz)
         Prepreg: 0.2mm (7628) — εr ≈ 4.4
Layer 4: Signal (35µm Cu, 1oz)

Total: ~1.6mm (standard)
```

**Why this stackup:**
1. **L1 (Top)**: High-speed signals (USB, clocks) route here with L2 GND directly below → excellent return current path, controlled impedance
2. **L2 (GND)**: Solid, unbroken ground plane — the most critical layer for signal integrity and EMC
3. **L3 (Power)**: Power distribution + can route low-speed signals in gaps. Keep power islands separated (analog/digital) with ferrite bead connection
4. **L4 (Bottom)**: Components and remaining signals, return path via L3

**USB 2.0 routing on this stackup:**
- Differential impedance: 90Ω ±10% (USB 2.0 spec)
- Trace width: ~0.15mm with ~0.18mm gap (for h=0.2mm, εr=4.4)
- Length matching: D+ and D- within ±2mm (±150ps at 480Mbps)
- Max trace length: <150mm to avoid signal degradation
- Keep USB traces on L1 only — no vias, no layer transitions

**Mixed-signal partitioning:**
```
┌──────────────────────────────────────┐
│  Digital Section    │  Analog Section │
│  ┌──────────┐      │  ┌──────────┐  │
│  │ MCU      │      │  │ ADC/DAC  │  │
│  │ USB PHY  │      │  │ Op-amps  │  │
│  │ SMPS     │      │  │ Sensors  │  │
│  └──────────┘      │  └──────────┘  │
│                    │                 │
│ ═══ Digital GND ═══│═ Analog GND ══ │
│         └──── single point ────┘    │
└──────────────────────────────────────┘
```

**DRC rules in KiCad for this stackup:**
- USB traces: Net Class "USB" → width 0.15mm, clearance 0.2mm
- Power traces: Net Class "Power" → width 0.5mm min
- Default: width 0.25mm, clearance 0.15mm
- Via: 0.4mm drill, 0.8mm annular ring

**KiCad Board Setup:**
Board Setup → Physical Stackup → set layer thicknesses to match your fab's actual stackup.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to set up DRC rules in KiCad 8 for JLCPCB manufacturing capabilities?",
            },
            {
                "from": "gpt",
                "value": """KiCad 8 DRC setup for JLCPCB manufacturing:

**Board Setup → Design Rules → Constraints:**

```
Minimum track width:           0.127mm (5mil) — JLCPCB min
Minimum clearance:             0.127mm (5mil)
Minimum via drill:             0.3mm — JLCPCB standard
Minimum via annular ring:      0.15mm (pad = drill + 2×0.15 = 0.6mm min)
Minimum through-hole drill:    0.3mm
Min silkscreen width:          0.15mm
Min silkscreen clearance:      0.15mm
Minimum hole-to-hole:          0.254mm (10mil)
Board edge clearance:          0.3mm (copper to edge)
```

**Net Classes (Board Setup → Design Rules → Net Classes):**

| Net Class | Width | Clearance | Via Drill | Via Diameter |
|-----------|-------|-----------|-----------|-------------|
| Default | 0.25mm | 0.15mm | 0.3mm | 0.6mm |
| Power | 0.5mm | 0.2mm | 0.4mm | 0.8mm |
| USB | 0.15mm | 0.2mm | — | — |
| High Current | 1.0mm | 0.3mm | 0.5mm | 1.0mm |

**Custom Rules (Board Setup → Design Rules → Custom Rules):**

```
# JLCPCB minimum annular ring
(rule "JLCPCB_annular_ring"
    (constraint annular_width (min 0.13mm))
)

# Minimum solder mask bridge
(rule "JLCPCB_solder_mask"
    (constraint solder_mask_bridge (min 0.1mm))
)

# Board edge clearance
(rule "JLCPCB_edge_clearance"
    (constraint edge_clearance (min 0.3mm))
)

# Silk to pad clearance
(rule "silk_to_pad"
    (constraint silk_clearance (min 0.15mm))
)
```

**Gerber generation for JLCPCB:**
File → Plot → Plot Format: Gerber
- Layers: F.Cu, B.Cu, In1.Cu, In2.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask, Edge.Cuts
- ✓ Use Protel filename extensions
- ✓ Subtract soldermask from silkscreen
- Coordinate format: 4.6
- Generate drill files: Excellon, PTH and NPTH in single file

**Naming convention (JLCPCB auto-detect):**
```
project-F_Cu.gtl       # Front copper
project-B_Cu.gbl       # Back copper
project-F_SilkS.gto    # Front silkscreen
project-B_SilkS.gbo    # Back silkscreen
project-F_Mask.gts      # Front soldermask
project-B_Mask.gbs      # Back soldermask
project-Edge_Cuts.gm1   # Board outline
project.drl              # Drill file
```

Zip all files → upload to jlcpcb.com/quote""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to route differential pairs in KiCad for USB 3.0 or Ethernet?",
            },
            {
                "from": "gpt",
                "value": """Differential pair routing in KiCad 8/9:

**Step 1: Define differential pairs in schematic**

In Eeschema, name nets with `+`/`-` suffix:
```
USB3_TX+ / USB3_TX-
USB3_RX+ / USB3_RX-
ETH_TX+ / ETH_TX-
ETH_RX+ / ETH_RX-
```

KiCad auto-detects `+/-` or `P/N` suffix as differential pairs.

**Step 2: Configure Net Class**

Board Setup → Design Rules → Net Classes:

| Protocol | Z_diff | Trace W | Gap | Via |
|----------|--------|---------|-----|-----|
| USB 2.0 | 90Ω | 0.15mm | 0.18mm | Avoid |
| USB 3.0 | 85Ω | 0.13mm | 0.15mm | Avoid |
| Gigabit Ethernet | 100Ω | 0.12mm | 0.20mm | Avoid |
| PCIe | 85Ω | 0.13mm | 0.15mm | Min |

**Step 3: Route differential pairs**

1. Select the interactive router: `X` key
2. Switch to differential pair mode: `D` key (or Route → Route Differential Pair)
3. Click on one pad of the pair — KiCad auto-selects the complementary pad
4. Route both traces simultaneously maintaining constant gap

**Key routing rules:**

```
┌──────────────────────────────────────────────┐
│                                              │
│  ✓ DO:                                       │
│  • Keep traces parallel with constant gap    │
│  • Route on layers adjacent to ground plane  │
│  • Length-match within pair: ±5mil (USB 2.0) │
│  •                          ±2mil (USB 3.0)  │
│  • Use arc corners (45° minimum)             │
│  • Add ground vias near signal vias          │
│                                              │
│  ✗ DON'T:                                    │
│  • Split ground plane under diff pair        │
│  • Route near board edges (<3× trace width)  │
│  • Cross other high-speed signals            │
│  • Change layers mid-pair (if possible)      │
│  • Put components between the pair traces    │
│                                              │
└──────────────────────────────────────────────┘
```

**Step 4: Length matching**

1. Route the pair normally
2. Select the shorter trace
3. Route → Tune Differential Pair Skew (or shortcut `9`)
4. Click on the trace → move mouse to add serpentine
5. Check: Inspect → Design Rule Check → verify diff pair length

**KiCad Custom DRC rule for USB 3.0:**
```
(rule "USB3_diff_pair"
    (condition "A.NetClass == 'USB3'")
    (constraint diff_pair_gap (min 0.12mm) (opt 0.15mm) (max 0.20mm))
    (constraint diff_pair_uncoupled (max 5mm))
)
```

**Impedance verification:**
Use KiCad's built-in calculator (Inspect → Calculator → TransLine) or Saturn PCB Toolkit to verify Z_diff matches target for your actual stackup.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a KiCad Python script to export BOM in JLCPCB format from a schematic.",
            },
            {
                "from": "gpt",
                "value": """KiCad Python BOM export for JLCPCB SMT assembly:

```python
#!/usr/bin/env python3
\"\"\"Generate JLCPCB-compatible BOM CSV from KiCad schematic.

JLCPCB BOM format requires:
  Comment, Designator, Footprint, LCSC Part Number

Run: python3 bom_jlcpcb.py project.kicad_sch
\"\"\"

import csv
import sys
import re
from collections import defaultdict


def parse_kicad_sch(filepath):
    \"\"\"Parse .kicad_sch file and extract component info.\"\"\"
    components = []
    with open(filepath, 'r') as f:
        content = f.read()

    # Find all symbol instances
    symbol_blocks = re.findall(
        r'\\(symbol\\s+\\(lib_id\\s+"([^"]+)"\\).*?'
        r'\\(property\\s+"Reference"\\s+"([^"]+)".*?'
        r'\\(property\\s+"Value"\\s+"([^"]+)".*?'
        r'\\(property\\s+"Footprint"\\s+"([^"]+)".*?'
        r'(?:\\(property\\s+"LCSC"\\s+"([^"]*)")?',
        content, re.DOTALL
    )

    for lib_id, ref, value, footprint, lcsc in symbol_blocks:
        # Skip power symbols, test points, mounting holes
        if ref.startswith(('#', 'TP', 'MH', 'H')) or 'power' in lib_id.lower():
            continue

        components.append({
            'reference': ref,
            'value': value,
            'footprint': footprint.split(':')[-1] if ':' in footprint else footprint,
            'lcsc': lcsc or '',
        })

    return components


def group_components(components):
    \"\"\"Group identical components (same value + footprint + LCSC).\"\"\"
    groups = defaultdict(list)
    for comp in components:
        key = (comp['value'], comp['footprint'], comp['lcsc'])
        groups[key].append(comp['reference'])

    rows = []
    for (value, footprint, lcsc), refs in sorted(groups.items()):
        refs_sorted = sorted(refs, key=lambda r: (r[0], int(re.search(r'\\d+', r).group())))
        rows.append({
            'Comment': value,
            'Designator': ', '.join(refs_sorted),
            'Footprint': footprint,
            'LCSC': lcsc,
            'Quantity': len(refs_sorted),
        })

    return rows


def export_csv(rows, output_path):
    \"\"\"Write JLCPCB BOM CSV.\"\"\"
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'Comment', 'Designator', 'Footprint', 'LCSC', 'Quantity'
        ])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 bom_jlcpcb.py <project.kicad_sch>")
        sys.exit(1)

    sch_file = sys.argv[1]
    output = sch_file.replace('.kicad_sch', '_bom_jlcpcb.csv')

    components = parse_kicad_sch(sch_file)
    rows = group_components(components)
    export_csv(rows, output)

    print(f"Exported {len(rows)} BOM lines ({sum(r['Quantity'] for r in rows)} components)")
    print(f"Output: {output}")

    # Warn about missing LCSC numbers
    missing = [r for r in rows if not r['LCSC']]
    if missing:
        print(f"\\nWarning: {len(missing)} parts without LCSC number:")
        for r in missing:
            print(f"  {r['Designator']}: {r['Comment']} ({r['Footprint']})")
```

**Adding LCSC numbers in KiCad:**
1. In Eeschema, double-click component → Add Field
2. Field name: `LCSC`
3. Field value: e.g., `C25804` (from jlcpcb.com/parts)

**CPL (Component Placement List) for JLCPCB:**
Generate from KiCad: File → Fabrication Outputs → Component Placement
- Format: CSV
- Rename columns: `Ref` → `Designator`, `PosX` → `Mid X`, `PosY` → `Mid Y`, `Rot` → `Rotation`, `Side` → `Layer`""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "What are the IPC-2221 conductor spacing requirements for different voltages?",
            },
            {
                "from": "gpt",
                "value": """IPC-2221 conductor spacing (clearance) table:

**Table 6-1: Minimum conductor spacing (internal layers, uncoated):**

| Voltage (DC or AC peak) | B1 (Internal) | B2 (External, uncoated) | B3 (External, coated) | B4 (External, >3048m) |
|--------------------------|--------------|------------------------|----------------------|----------------------|
| 0-15V | 0.05mm (2mil) | 0.1mm (4mil) | 0.05mm (2mil) | 0.1mm (4mil) |
| 16-30V | 0.05mm (2mil) | 0.1mm (4mil) | 0.05mm (2mil) | 0.1mm (4mil) |
| 31-50V | 0.1mm (4mil) | 0.6mm (25mil) | 0.13mm (5mil) | 0.6mm (25mil) |
| 51-100V | 0.1mm (4mil) | 0.6mm (25mil) | 0.13mm (5mil) | 1.5mm |
| 101-150V | 0.2mm (8mil) | 0.6mm (25mil) | 0.4mm | 3.2mm |
| 151-170V | 0.2mm (8mil) | 1.25mm | 0.4mm | 3.2mm |
| 171-250V | 0.2mm (8mil) | 1.25mm | 0.4mm | 6.4mm |
| 251-300V | 0.2mm (8mil) | 1.25mm | 0.8mm | 12.5mm |
| 301-500V | 0.25mm (10mil) | 2.5mm | 0.8mm | 12.5mm |

**Key categories:**
- **B1 (Internal)**: Conductors on internal layers, protected by laminate
- **B2 (External, uncoated)**: Sea level, uncoated external conductors
- **B3 (External, coated)**: Conformal coated external conductors
- **B4 (Altitude)**: Above 3048m (10,000 ft) — air is thinner, lower breakdown voltage

**Practical guidelines:**

1. **Low voltage (<50V)**: 0.15mm (6mil) clearance is safe for most applications. KiCad default 0.2mm is conservative and fine.

2. **Mains voltage (230V AC)**: Peak = 325V
   - Internal: 0.2mm minimum
   - External uncoated: 1.25mm minimum
   - **Creepage** (along surface): 2.5mm minimum per IEC 60950
   - **Slots** in PCB between primary/secondary: recommended

3. **High voltage (>500V)**: Consult IPC-2221 directly + consider IEC 62368-1

**In KiCad — setting per-net clearances:**
```
# Custom DRC rule for high-voltage nets
(rule "HV_clearance"
    (condition "A.NetClass == 'HighVoltage' || B.NetClass == 'HighVoltage'")
    (constraint clearance (min 2.5mm))
)

(rule "mains_clearance"
    (condition "A.NetClass == 'Mains' || B.NetClass == 'Mains'")
    (constraint clearance (min 1.25mm))
)
```

**Remember:** IPC-2221 gives MINIMUM spacing. Always add margin. For safety-critical designs, use IEC 60950-1 or IEC 62368-1 creepage/clearance tables instead.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to design a proper ground pour in KiCad with via stitching?",
            },
            {
                "from": "gpt",
                "value": """Ground pour and via stitching in KiCad 8:

**Step 1: Create ground pour (copper zone)**

1. Select copper zone tool (`Add Filled Zone` or shortcut `B` to draw)
2. Click on F.Cu (or B.Cu)
3. Zone properties:
   - Net: GND
   - Clearance: 0.3mm (from other nets)
   - Min width: 0.2mm
   - Pad connection: Thermal relief
   - Thermal relief gap: 0.3mm
   - Thermal relief spoke width: 0.5mm
   - Zone priority: 0 (lowest)
   - Fill type: Solid
4. Draw the zone outline around the board edge
5. Press `B` to fill all zones

**Step 2: Via stitching**

KiCad 8/9 has built-in via stitching:

1. Place → Via Stitching → Add Via Stitching
2. Or use the "Add Vias" tool with GND net selected

**Manual via stitching pattern:**
```
┌─────────────────────────────────────┐
│ o   o   o   o   o   o   o   o   o  │
│                                     │
│ o       o       o       o       o  │
│                                     │
│ o   o   o   o   o   o   o   o   o  │
│         ┌─────────────┐            │
│ o       │   IC / RF   │       o    │
│         │   section   │            │
│ o       └─────────────┘       o    │
│                                     │
│ o   o   o   o   o   o   o   o   o  │
│                                     │
│ o       o       o       o       o  │
│                                     │
│ o   o   o   o   o   o   o   o   o  │
└─────────────────────────────────────┘
```

**Via stitching rules:**
- Spacing: every λ/20 at max operating frequency
  - 100MHz → λ = 3m → spacing ≤ 150mm (not critical)
  - 1GHz → λ = 0.3m → spacing ≤ 15mm
  - 2.4GHz → λ = 0.125m → spacing ≤ 6mm
- Via size: 0.3mm drill, 0.6mm pad (standard manufacturing)
- Density: higher near RF sections, connectors, and board edges
- Pattern: grid or perimeter "fence" around sensitive areas

**KiCad Python script for via stitching grid:**
```python
import pcbnew

def add_via_stitching(board, net_name="GND", spacing_mm=5.0,
                       drill_mm=0.3, size_mm=0.6):
    \"\"\"Add via stitching grid across the board.\"\"\"
    net = board.FindNet(net_name)
    if not net:
        print(f"Net '{net_name}' not found")
        return

    bbox = board.GetBoardEdgesBoundingBox()
    x_start = bbox.GetLeft()
    y_start = bbox.GetTop()
    x_end = bbox.GetRight()
    y_end = bbox.GetBottom()

    spacing = int(spacing_mm * 1e6)
    count = 0

    x = x_start + spacing
    while x < x_end - spacing:
        y = y_start + spacing
        while y < y_end - spacing:
            pos = pcbnew.VECTOR2I(x, y)

            # Check if position is inside board outline and not on a pad
            if board.GetBoardEdgesBoundingBox().Contains(pos):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pos)
                via.SetNet(net)
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetDrill(int(drill_mm * 1e6))
                via.SetWidth(int(size_mm * 1e6))
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                board.Add(via)
                count += 1

            y += spacing
        x += spacing

    pcbnew.Refresh()
    print(f"Added {count} stitching vias")

# Usage:
add_via_stitching(pcbnew.GetBoard(), spacing_mm=5.0)
```

**Ground pour checklist:**
- [ ] GND zone on every copper layer
- [ ] No islands (disconnected copper) — DRC will catch these
- [ ] Thermal relief on GND pads (for soldering)
- [ ] Direct connect (no relief) on high-current GND pads
- [ ] Via stitching connects all ground planes
- [ ] No ground plane splits under high-speed signals""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How do I calculate trace width for a given current in KiCad?",
            },
            {
                "from": "gpt",
                "value": """Trace width for current carrying capacity (IPC-2221):

**Formula (IPC-2152, simplified):**
```
I = k × ΔT^0.44 × A^0.725

Where:
  I = current (Amps)
  k = 0.048 (external layers) or 0.024 (internal layers)
  ΔT = temperature rise above ambient (°C)
  A = cross-sectional area (mil²) = width(mil) × thickness(mil)
```

**Quick reference table (1oz copper = 35µm, 10°C rise, external):**

| Current | External Width | Internal Width |
|---------|---------------|----------------|
| 0.5A | 0.25mm (10mil) | 0.5mm (20mil) |
| 1.0A | 0.5mm (20mil) | 1.0mm (40mil) |
| 2.0A | 1.2mm (47mil) | 2.4mm (95mil) |
| 3.0A | 2.0mm (79mil) | 4.0mm (158mil) |
| 5.0A | 4.0mm (157mil) | 8.0mm (315mil) |
| 10A | 10mm (394mil) | 20mm (787mil) |

**For 20°C rise (more common):**

| Current | External Width | Internal Width |
|---------|---------------|----------------|
| 1.0A | 0.3mm (12mil) | 0.6mm (24mil) |
| 2.0A | 0.7mm (28mil) | 1.4mm (55mil) |
| 3.0A | 1.2mm (47mil) | 2.4mm (95mil) |
| 5.0A | 2.4mm (95mil) | 4.8mm (189mil) |

**Using 2oz copper (70µm) halves the width** for same current.

**In KiCad:**
1. Inspect → Board Statistics → Calculator → Track Width
2. Or use Net Classes: Board Setup → Design Rules → Net Classes
   - Create "Power" net class with wider traces
   - Assign power nets (VCC, 5V, 3V3, VBAT) to this class

**Thermal vias for heat dissipation:**
For high-current paths on internal layers, add thermal vias along the trace:
```
═══════╤══════╤══════╤══════╤═══════
       │      │      │      │
═══════╧══════╧══════╧══════╧═══════
       vias connect to matching trace on other layer
```

**Practical tips:**
- Always calculate for INTERNAL layers (worst case — less cooling)
- Add 50% margin to calculated width
- For >5A: consider polygon pour instead of traces
- Voltage drop: V = I × R, where R = ρ × L / (w × t)
  - ρ(Cu) = 1.72×10⁻⁸ Ω·m
  - For 10A over 50mm in 0.5mm/1oz: V_drop = 49mV""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Explain the KiCad file formats and how to parse .kicad_pcb programmatically.",
            },
            {
                "from": "gpt",
                "value": """KiCad file formats (v8/v9) and parsing:

**File types:**
| Extension | Content | Format |
|-----------|---------|--------|
| `.kicad_pro` | Project settings | S-expression |
| `.kicad_sch` | Schematic | S-expression |
| `.kicad_pcb` | PCB layout | S-expression |
| `.kicad_mod` | Footprint | S-expression |
| `.kicad_sym` | Symbol library | S-expression |
| `.kicad_dru` | Custom DRC rules | Text |
| `.kicad_wks` | Worksheet/titleblock | S-expression |

**S-expression format (all KiCad files):**
```lisp
(kicad_pcb
  (version 20240108)
  (generator "pcbnew")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
  )
  (net 0 "")
  (net 1 "GND")
  (net 2 "VCC")

  (footprint "Package_QFP:LQFP-48_7x7mm_P0.5mm"
    (layer "F.Cu")
    (at 100 80)
    (pad "1" smd roundrect
      (at -3.75 -2.5)
      (size 0.3 0.8)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (net 15 "PA0")
    )
  )

  (segment
    (start 100.5 80.2)
    (end 105.3 80.2)
    (width 0.25)
    (layer "F.Cu")
    (net 15)
  )

  (via
    (at 105.3 80.2)
    (size 0.6)
    (drill 0.3)
    (layers "F.Cu" "B.Cu")
    (net 15)
  )
)
```

**Python parsing (without KiCad API):**

```python
import re
from dataclasses import dataclass

def parse_sexpr(text):
    \"\"\"Simple S-expression parser for KiCad files.\"\"\"
    tokens = re.findall(r'\\(|\\)|"[^"]*"|[^\\s()]+', text)
    stack = [[]]
    for token in tokens:
        if token == '(':
            stack.append([])
        elif token == ')':
            node = stack.pop()
            stack[-1].append(node)
        else:
            # Strip quotes
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]
            stack[-1].append(token)
    return stack[0][0] if stack[0] else []

def extract_nets(pcb_file):
    \"\"\"Extract all nets from a .kicad_pcb file.\"\"\"
    with open(pcb_file, 'r') as f:
        content = f.read()
    nets = re.findall(r'\\(net\\s+(\\d+)\\s+"([^"]*)"\\)', content)
    return {int(num): name for num, name in nets}

def extract_footprints(pcb_file):
    \"\"\"Extract footprint positions and references.\"\"\"
    with open(pcb_file, 'r') as f:
        content = f.read()
    # Find all footprint blocks
    fps = re.findall(
        r'\\(footprint\\s+"([^"]+)".*?'
        r'\\(at\\s+([\\d.]+)\\s+([\\d.]+)(?:\\s+[\\d.]+)?\\).*?'
        r'\\(property\\s+"Reference"\\s+"([^"]+)"',
        content, re.DOTALL
    )
    return [{'footprint': fp, 'x': float(x), 'y': float(y), 'ref': ref}
            for fp, x, y, ref in fps]

# Usage:
nets = extract_nets("project.kicad_pcb")
components = extract_footprints("project.kicad_pcb")
for comp in components:
    print(f"{comp['ref']}: {comp['footprint']} at ({comp['x']}, {comp['y']})")
```

**Using KiCad Python API (inside KiCad):**
```python
import pcbnew
board = pcbnew.LoadBoard("project.kicad_pcb")

# Iterate all footprints
for fp in board.GetFootprints():
    print(f"{fp.GetReference()}: {fp.GetFPID().GetUniStringLibItemName()}")
    print(f"  Position: {fp.GetPosition()}")
    print(f"  Layer: {fp.GetLayerName()}")
    for pad in fp.Pads():
        print(f"  Pad {pad.GetNumber()}: net={pad.GetNetname()}")

# Iterate all tracks
for track in board.GetTracks():
    if isinstance(track, pcbnew.PCB_TRACK):
        print(f"Track: {track.GetNetname()} width={track.GetWidth()/1e6}mm")
    elif isinstance(track, pcbnew.PCB_VIA):
        print(f"Via: {track.GetNetname()} drill={track.GetDrill()/1e6}mm")
```""",
            },
        ]
    },
]


KICAD_KEYWORDS = [
    "kicad",
    "pcb",
    "footprint",
    "schematic",
    "eeschema",
    "pcbnew",
    "gerber",
    "drill",
    "excellon",
    "bom",
    "netlist",
    "drc",
    "routing",
    "trace",
    "via",
    "copper",
    "solder",
    "pad",
    "silkscreen",
    "soldermask",
    "courtyard",
    "stackup",
    "impedance",
    "microstrip",
    "stripline",
    "differential pair",
    "ground plane",
    "power plane",
    "copper pour",
    "ipc-2221",
    "ipc-7351",
    "ipc-a-610",
    "eda",
    "cad",
    "layout",
    "placement",
    "jlcpcb",
    "pcbway",
    "oshpark",
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download and convert KiCad/PCB datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. STEM-AI Electrical Engineering (25% KiCad + 10% KiCad Python)
    print("  Downloading STEM-AI-mtl/Electrical-engineering...")
    try:
        ds = load_dataset(
            "STEM-AI-mtl/Electrical-engineering", split="train", streaming=True
        )
        count = 0
        for row in ds:
            question = (
                row.get("question", "")
                or row.get("instruction", "")
                or row.get("title", "")
            )
            answer = (
                row.get("answer", "")
                or row.get("output", "")
                or row.get("response", "")
            )
            if not question or not answer or len(answer) < 50:
                continue
            combined = (question + " " + answer).lower()
            if any(kw in combined for kw in KICAD_KEYWORDS):
                samples.append(
                    {
                        "conversations": [
                            {"from": "system", "value": SYSTEM_PROMPT},
                            {"from": "human", "value": question.strip()},
                            {"from": "gpt", "value": answer.strip()},
                        ]
                    }
                )
                count += 1
                if count >= max_samples:
                    break
        print(f"    Got {count} KiCad/PCB examples from STEM-AI")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. Electronics StackExchange (filter for PCB/KiCad)
    # Columns: Id, Tags, Answer, Body, Title, CreationDate
    print("  Downloading bshada/electronics.stackexchange.com (PCB/KiCad filter)...")
    try:
        ds = load_dataset(
            "bshada/electronics.stackexchange.com", split="train", streaming=True
        )
        count = 0
        for row in ds:
            title = row.get("Title", "")
            body = row.get("Body", "")
            answer = row.get("Answer", "")
            tags = row.get("Tags", "")
            if not title or not answer or len(answer) < 100:
                continue
            combined = (title + " " + body + " " + answer + " " + tags).lower()
            if not any(kw in combined for kw in KICAD_KEYWORDS):
                continue
            question = re.sub(r"<[^>]+>", "", title + "\n" + body).strip()
            answer_clean = re.sub(r"<[^>]+>", "", answer).strip()
            if len(answer_clean) < 80:
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question[:1000]},
                        {"from": "gpt", "value": answer_clean[:4000]},
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Electronics SE (PCB/KiCad) examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(description="Build KiCad/PCB fine-tuning dataset")
    parser.add_argument(
        "--with-hf", action="store_true", help="Include HuggingFace datasets"
    )
    parser.add_argument(
        "--max-samples", type=int, default=2000, help="Max HF samples per source"
    )
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "kicad_chat.jsonl")

    all_samples = list(SEED_EXAMPLES)
    print(f"  {len(SEED_EXAMPLES)} seed examples")

    if args.with_hf:
        hf_samples = build_from_huggingface(args.max_samples)
        all_samples.extend(hf_samples)

    with open(output_path, "w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n  Wrote {len(all_samples)} examples to {output_path}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")
    if not args.with_hf:
        print(
            "\n  To enrich: python build_kicad_dataset.py --with-hf --max-samples 2000"
        )


if __name__ == "__main__":
    main()
