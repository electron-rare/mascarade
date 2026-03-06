#!/usr/bin/env python3
"""Build fine-tuning dataset for FreeCAD / OpenSCAD / parametric CAD domain.

Covers: FreeCAD Python scripting, OpenSCAD code, parametric modeling,
        CadQuery, 3D printing, mechanical design automation.

Usage:
  python build_freecad_dataset.py                # Seeds only
  python build_freecad_dataset.py --with-hf      # Seeds + HuggingFace datasets
"""

import argparse
import json
import os

SYSTEM_PROMPT = (
    "You are an expert in parametric 3D CAD modeling and automation. "
    "You write FreeCAD Python scripts (Part, PartDesign, Sketcher, Draft), "
    "OpenSCAD code, and CadQuery scripts for mechanical parts and assemblies. "
    "You understand constraints, boolean operations, extrusions, revolves, "
    "fillets, chamfers, and design-for-manufacturing principles. "
    "You provide complete, runnable code with clear parameter definitions."
)

SEED_EXAMPLES = [
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a FreeCAD Python script to create a parametric enclosure box with lid, mounting holes, and ventilation slots.",
            },
            {
                "from": "gpt",
                "value": """FreeCAD Python script for a parametric enclosure:

```python
import FreeCAD
import Part

# Parameters
length = 100  # mm
width = 60
height = 40
wall = 2.0
lid_height = 8
hole_d = 3.2  # M3 mounting holes
hole_inset = 5
slot_w = 1.5
slot_h = 15
slot_count = 6
slot_spacing = 4

doc = FreeCAD.newDocument("Enclosure")

# --- Box body ---
outer = Part.makeBox(length, width, height)
inner = Part.makeBox(
    length - 2*wall, width - 2*wall, height - wall,
    FreeCAD.Vector(wall, wall, wall)
)
body = outer.cut(inner)

# Mounting holes (4 corners)
for x in [hole_inset, length - hole_inset]:
    for y in [hole_inset, width - hole_inset]:
        cyl = Part.makeCylinder(hole_d/2, wall + 1, FreeCAD.Vector(x, y, -0.5))
        body = body.cut(cyl)
        # Bosses
        boss = Part.makeCylinder(hole_d/2 + 2, height - wall, FreeCAD.Vector(x, y, wall))
        boss_hole = Part.makeCylinder(hole_d/2, height - wall, FreeCAD.Vector(x, y, wall))
        body = body.fuse(boss).cut(boss_hole)

# Ventilation slots on one side
slot_start_x = (length - (slot_count * slot_w + (slot_count-1) * slot_spacing)) / 2
for i in range(slot_count):
    sx = slot_start_x + i * (slot_w + slot_spacing)
    slot = Part.makeBox(slot_w, wall + 1, slot_h,
        FreeCAD.Vector(sx, -0.5, height/2 - slot_h/2))
    body = body.cut(slot)

body_obj = doc.addObject("Part::Feature", "Body")
body_obj.Shape = body

# --- Lid ---
lid_outer = Part.makeBox(length, width, lid_height)
lid_inner = Part.makeBox(
    length - 2*wall, width - 2*wall, lid_height - wall,
    FreeCAD.Vector(wall, wall, wall)
)
# Lip that fits inside box
lip = Part.makeBox(
    length - 2*wall - 0.4, width - 2*wall - 0.4, 3,
    FreeCAD.Vector(wall + 0.2, wall + 0.2, -3)
)
lid = lid_outer.cut(lid_inner).fuse(lip)

# Lid mounting holes
for x in [hole_inset, length - hole_inset]:
    for y in [hole_inset, width - hole_inset]:
        cyl = Part.makeCylinder(hole_d/2, lid_height + 1, FreeCAD.Vector(x, y, -0.5))
        lid = lid.cut(cyl)

lid_obj = doc.addObject("Part::Feature", "Lid")
lid_obj.Shape = lid
lid_obj.Placement.Base = FreeCAD.Vector(0, 0, height + 10)

doc.recompute()
```

Key design choices:
- 0.4mm clearance on lid lip for 3D printing tolerance
- M3 mounting bosses with 2mm wall around hole
- Ventilation slots centered on front face
- Parametric: change variables at top to resize everything""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write an OpenSCAD script for a parametric gear with configurable module, teeth count, and pressure angle.",
            },
            {
                "from": "gpt",
                "value": """Parametric involute gear in OpenSCAD:

```openscad
// Parametric Involute Spur Gear
// Parameters
module_val = 2;        // Module (mm)
teeth = 20;            // Number of teeth
pressure_angle = 20;   // Pressure angle (degrees)
thickness = 10;        // Gear thickness (mm)
bore_d = 8;            // Center bore diameter
hub_d = 16;            // Hub diameter
hub_h = 5;             // Hub height above gear

// Derived values
pitch_d = module_val * teeth;
addendum = module_val;
dedendum = 1.25 * module_val;
outer_d = pitch_d + 2 * addendum;
root_d = pitch_d - 2 * dedendum;
base_d = pitch_d * cos(pressure_angle);

// Involute point at parameter t
function involute_x(r, t) = r * (cos(t) + t * PI/180 * sin(t));
function involute_y(r, t) = r * (sin(t) - t * PI/180 * cos(t));

// Generate tooth profile points
function tooth_profile(steps=20) = [
    for (i = [0:steps])
        let(t = i * 30 / steps)
        [involute_x(base_d/2, t), involute_y(base_d/2, t)]
];

module gear_tooth() {
    // Simplified tooth using polygon approximation
    tooth_angle = 360 / teeth;
    half_tooth = tooth_angle / 4;

    rotate([0, 0, -half_tooth])
    linear_extrude(height = thickness)
    polygon(points = concat(
        [[root_d/2 * cos(-half_tooth), root_d/2 * sin(-half_tooth)]],
        [for (a = [-half_tooth : half_tooth/10 : half_tooth])
            [(root_d/2 + (outer_d/2 - root_d/2) *
              pow(cos((a/half_tooth) * 45), 0.8)) * cos(a),
             (root_d/2 + (outer_d/2 - root_d/2) *
              pow(cos((a/half_tooth) * 45), 0.8)) * sin(a)]],
        [[root_d/2 * cos(half_tooth), root_d/2 * sin(half_tooth)]]
    ));
}

module gear() {
    difference() {
        union() {
            // Gear body with teeth
            for (i = [0:teeth-1]) {
                rotate([0, 0, i * 360/teeth])
                gear_tooth();
            }
            // Root circle
            linear_extrude(height = thickness)
            circle(d = root_d, $fn = teeth * 4);
            // Hub
            translate([0, 0, thickness])
            linear_extrude(height = hub_h)
            circle(d = hub_d, $fn = 64);
        }
        // Center bore
        translate([0, 0, -1])
        linear_extrude(height = thickness + hub_h + 2)
        circle(d = bore_d, $fn = 64);
        // Keyway (optional)
        translate([-bore_d/4, bore_d/2 - 1, -1])
        cube([bore_d/2, 2, thickness + hub_h + 2]);
    }
}

gear();
```

Usage: Change `teeth`, `module_val`, `bore_d` to customize. For meshing gears, use same module and pressure angle. Center distance = (teeth1 + teeth2) × module / 2.""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "Write a CadQuery script for a PCB standoff with M3 thread hole, hex base, and snap-fit clip.",
            },
            {
                "from": "gpt",
                "value": """CadQuery PCB standoff with snap-fit:

```python
import cadquery as cq

# Parameters
standoff_h = 10      # Total height
hex_size = 5.5       # Hex flat-to-flat (M3 nut = 5.5mm)
hole_d = 2.5         # M3 tap drill
clip_h = 3           # Snap-fit clip height
clip_w = 4           # Clip width
clip_gap = 1.6       # Gap for PCB (1.6mm standard)
pcb_hole_d = 3.2     # PCB mounting hole
wall = 0.8           # Clip wall thickness

# Hex base with threaded hole
base = (
    cq.Workplane("XY")
    .polygon(6, hex_size / (3**0.5 / 2))  # circumscribed hex
    .extrude(standoff_h)
    .faces(">Z").workplane()
    .hole(hole_d, standoff_h)  # through-hole for M3
)

# Snap-fit clip on top
clip = (
    cq.Workplane("XY")
    .workplane(offset=standoff_h)
    # Outer cylinder
    .circle(pcb_hole_d/2 + wall)
    .extrude(clip_h + clip_gap)
    # Hollow inside
    .faces(">Z").workplane()
    .hole(pcb_hole_d, clip_h + clip_gap)
)

# Cut slots for flex (2 opposing slots)
slot = (
    cq.Workplane("XZ")
    .workplane(offset=0)
    .center(0, standoff_h + clip_gap)
    .rect(0.6, clip_h)
    .extrude(pcb_hole_d + 2*wall + 1, both=True)
)

# Barb (outward bump for retention)
barb = (
    cq.Workplane("XY")
    .workplane(offset=standoff_h + clip_gap + clip_h - 0.5)
    .circle(pcb_hole_d/2 + wall + 0.3)
    .circle(pcb_hole_d/2 + wall)
    .extrude(0.5)
)

result = base.union(clip).cut(slot).union(barb)

# Export
cq.exporters.export(result, "pcb_standoff.step")
```

Print settings for FDM:
- Layer height: 0.12mm for clip detail
- No supports needed if printed upright
- Material: PETG or Nylon for flexibility
- Scale hex_size for M2.5 (5mm) or M4 (7mm) variants""",
            },
        ]
    },
    {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {
                "from": "human",
                "value": "How to create a parametric FreeCAD model using Sketcher constraints and PartDesign?",
            },
            {
                "from": "gpt",
                "value": """Parametric FreeCAD model using Sketcher + PartDesign:

```python
import FreeCAD
import Part
import Sketcher
import PartDesign

doc = FreeCAD.newDocument("Bracket")

# Create Body
body = doc.addObject('PartDesign::Body', 'Body')

# --- Base sketch on XY plane ---
sketch = body.newObject('Sketcher::SketchObject', 'BaseSketch')
sketch.AttachmentSupport = [(doc.getObject('XY_Plane'), '')]
sketch.MapMode = 'FlatFace'

# Draw L-shaped bracket profile
# Horizontal leg
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(40, 0, 0)))       # Line 0
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(40, 0, 0), FreeCAD.Vector(40, 5, 0)))       # Line 1
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(40, 5, 0), FreeCAD.Vector(5, 5, 0)))        # Line 2
# Vertical leg
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(5, 5, 0), FreeCAD.Vector(5, 30, 0)))        # Line 3
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(5, 30, 0), FreeCAD.Vector(0, 30, 0)))       # Line 4
sketch.addGeometry(Part.LineSegment(
    FreeCAD.Vector(0, 30, 0), FreeCAD.Vector(0, 0, 0)))        # Line 5

# Add constraints
sketch.addConstraint(Sketcher.Constraint('Coincident', 0, 2, 1, 1))  # connect lines
sketch.addConstraint(Sketcher.Constraint('Coincident', 1, 2, 2, 1))
sketch.addConstraint(Sketcher.Constraint('Coincident', 2, 2, 3, 1))
sketch.addConstraint(Sketcher.Constraint('Coincident', 3, 2, 4, 1))
sketch.addConstraint(Sketcher.Constraint('Coincident', 4, 2, 5, 1))
sketch.addConstraint(Sketcher.Constraint('Coincident', 5, 2, 0, 1))

# Dimensional constraints (parametric!)
sketch.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, 40))   # horiz length
sketch.addConstraint(Sketcher.Constraint('DistanceY', 5, 1, 4, 2, 30))   # vert height
sketch.addConstraint(Sketcher.Constraint('DistanceY', 0, 1, 1, 2, 5))    # thickness
sketch.addConstraint(Sketcher.Constraint('DistanceX', 2, 2, 2, 1, 35))   # inner width

# Fix origin
sketch.addConstraint(Sketcher.Constraint('Lock', 0, 1, 0, 0))

# --- Pad (extrude) ---
pad = body.newObject('PartDesign::Pad', 'Pad')
pad.Profile = sketch
pad.Length = 20  # mm depth

# --- Add mounting holes ---
hole_sketch = body.newObject('Sketcher::SketchObject', 'HoleSketch')
hole_sketch.AttachmentSupport = [(pad, 'Face6')]  # top face
hole_sketch.MapMode = 'FlatFace'

# Two holes
hole_sketch.addGeometry(Part.Circle(FreeCAD.Vector(20, 10, 0), FreeCAD.Vector(0,0,1), 2.5))
hole_sketch.addGeometry(Part.Circle(FreeCAD.Vector(2.5, 20, 0), FreeCAD.Vector(0,0,1), 2.5))

pocket = body.newObject('PartDesign::Pocket', 'Holes')
pocket.Profile = hole_sketch
pocket.Type = 'Through'

# --- Fillet edges ---
fillet = body.newObject('PartDesign::Fillet', 'Fillet')
fillet.Base = [(pad, 'Edge8')]  # inner corner
fillet.Radius = 3

doc.recompute()
```

To make it truly parametric:
- Change dimensional constraint values to resize
- Use spreadsheet cells for named parameters
- Link constraints to spreadsheet: `sketch.setExpression('Constraints[0]', 'Spreadsheet.Length')`""",
            },
        ]
    },
]


def build_from_huggingface(max_samples: int) -> list[dict]:
    """Download CAD/3D datasets from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [!] pip install datasets — skipping HF download")
        return []

    samples = []

    # 1. Yas1n/FreeCAD_Sketches: 3000 FreeCAD Python scripts
    print("  Downloading Yas1n/FreeCAD_Sketches (3k FreeCAD scripts)...")
    try:
        ds = load_dataset("Yas1n/FreeCAD_Sketches", split="train", streaming=True)
        count = 0
        for row in ds:
            code = row.get("code", "") or row.get("text", "") or row.get("content", "")
            if not code or len(code) < 50:
                continue
            question = "Write a FreeCAD Python script to create a parametric sketch."
            # Try to extract description from comments
            for line in code.splitlines()[:5]:
                if line.strip().startswith("#") and len(line.strip()) > 10:
                    question = f"Write a FreeCAD Python script: {line.strip().lstrip('#').strip()}"
                    break
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": question},
                        {
                            "from": "gpt",
                            "value": f"FreeCAD sketch script:\n\n```python\n{code.strip()}\n```",
                        },
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} FreeCAD sketch examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 2. redcathode/thingiverse-openscad: OpenSCAD code from Thingiverse
    print("  Downloading redcathode/thingiverse-openscad...")
    try:
        ds = load_dataset(
            "redcathode/thingiverse-openscad", split="train", streaming=True
        )
        count = 0
        for row in ds:
            code = row.get("code", "") or row.get("scad", "") or row.get("text", "")
            prompt_text = row.get("prompt", "") or row.get("description", "")
            if not code or len(code) < 30:
                continue
            if not prompt_text:
                prompt_text = "Create a 3D model in OpenSCAD."
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": prompt_text.strip()[:500]},
                        {
                            "from": "gpt",
                            "value": f"OpenSCAD model:\n\n```openscad\n{code.strip()[:4000]}\n```",
                        },
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} Thingiverse OpenSCAD examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 3. ThomasTheMaker/OpenSCAD
    print("  Downloading ThomasTheMaker/OpenSCAD...")
    try:
        ds = load_dataset("ThomasTheMaker/OpenSCAD", split="train", streaming=True)
        count = 0
        for row in ds:
            code = row.get("code", "") or row.get("scad", "") or row.get("text", "")
            prompt_text = row.get("prompt", "") or row.get("description", "")
            if not code or len(code) < 30:
                continue
            if not prompt_text:
                prompt_text = "Write an OpenSCAD script for a 3D printable part."
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": prompt_text.strip()[:500]},
                        {
                            "from": "gpt",
                            "value": f"OpenSCAD script:\n\n```openscad\n{code.strip()[:4000]}\n```",
                        },
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} ThomasTheMaker OpenSCAD examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 4. adrlau/openscad-vision (OpenSCAD with images)
    print("  Downloading adrlau/openscad-vision...")
    try:
        ds = load_dataset("adrlau/openscad-vision", split="train", streaming=True)
        count = 0
        for row in ds:
            code = row.get("code", "") or row.get("scad", "") or row.get("text", "")
            desc = row.get("description", "") or row.get("prompt", "")
            if not code or len(code) < 30:
                continue
            if not desc:
                desc = "Create a 3D model in OpenSCAD."
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": desc.strip()[:500]},
                        {
                            "from": "gpt",
                            "value": f"OpenSCAD model:\n\n```openscad\n{code.strip()[:4000]}\n```",
                        },
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} openscad-vision examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 5. CADCODER/GenCAD-Code: 163k image→CadQuery pairs (text only)
    print("  Downloading CADCODER/GenCAD-Code (CadQuery code)...")
    try:
        ds = load_dataset("CADCODER/GenCAD-Code", split="train", streaming=True)
        count = 0
        for row in ds:
            code = row.get("cadquery", "") or row.get("code", "")
            prompt_text = row.get("prompt", "")
            if not code or len(code) < 50:
                continue
            if not prompt_text:
                prompt_text = "Write a CadQuery Python script for a 3D CAD model."
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {"from": "human", "value": prompt_text.strip()[:500]},
                        {
                            "from": "gpt",
                            "value": f"CadQuery script:\n\n```python\n{code.strip()[:4000]}\n```",
                        },
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} GenCAD-Code CadQuery examples")
    except Exception as e:
        print(f"    Failed: {e}")

    # 6. lanlanguai/CADLLM: 155k text→CAD command sequences
    print("  Downloading lanlanguai/CADLLM (text→CAD commands)...")
    try:
        ds = load_dataset("lanlanguai/CADLLM", split="train", streaming=True)
        count = 0
        for row in ds:
            desc = (
                row.get("description", "")
                or row.get("text", "")
                or row.get("prompt", "")
            )
            ccs = row.get("ccs", "") or row.get("commands", "") or row.get("output", "")
            if not desc or not ccs or len(ccs) < 20:
                continue
            samples.append(
                {
                    "conversations": [
                        {"from": "system", "value": SYSTEM_PROMPT},
                        {
                            "from": "human",
                            "value": f"Generate CAD commands for: {desc.strip()[:500]}",
                        },
                        {"from": "gpt", "value": ccs.strip()[:4000]},
                    ]
                }
            )
            count += 1
            if count >= max_samples:
                break
        print(f"    Got {count} CADLLM text→CAD examples")
    except Exception as e:
        print(f"    Failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Build FreeCAD/CAD fine-tuning dataset"
    )
    parser.add_argument(
        "--with-hf", action="store_true", help="Include HuggingFace datasets"
    )
    parser.add_argument(
        "--max-samples", type=int, default=2000, help="Max HF samples per source"
    )
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = args.output or os.path.join(output_dir, "freecad_chat.jsonl")

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
            "\n  To enrich: python build_freecad_dataset.py --with-hf --max-samples 2000"
        )


if __name__ == "__main__":
    main()
