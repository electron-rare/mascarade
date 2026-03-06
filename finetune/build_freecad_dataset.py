#!/usr/bin/env python3
"""Build FreeCAD dataset from various sources."""

import json
from pathlib import Path


def build_freecad_dataset():
    """Build FreeCAD dataset from existing examples and documentation."""

    dataset_path = Path("finetune/datasets/freecad_chat.jsonl")

    # Sample dataset entries
    dataset_entries = [
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for FreeCAD design and engineering.",
                },
                {
                    "role": "user",
                    "content": "How do I create a basic 3D part in FreeCAD?",
                },
                {
                    "role": "assistant",
                    "content": "To create a basic 3D part in FreeCAD: 1. Open FreeCAD and create a new document\n2. Switch to the Part Design workbench\n3. Click on 'Create sketch' and select a plane\n4. Draw your 2D profile using the sketch tools\n5. Close the sketch and use 'Pad' to extrude it into 3D\n6. Save your design as a .FCStd file.",
                },
            ]
        },
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for FreeCAD design and engineering.",
                },
                {
                    "role": "user",
                    "content": "What are the key differences between Part and Part Design workbenches?",
                },
                {
                    "role": "assistant",
                    "content": "Key differences: Part workbench uses constructive solid geometry (CSG) with boolean operations, while Part Design uses parametric feature-based modeling. Part Design maintains a history tree and is better for complex, editable designs. Part is simpler for basic operations and working with imported geometry.",
                },
            ]
        },
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for FreeCAD design and engineering.",
                },
                {
                    "role": "user",
                    "content": "How can I create custom macros in FreeCAD?",
                },
                {
                    "role": "assistant",
                    "content": "To create custom macros: 1. Go to Macro > Macros... > Create\n2. Write Python code using FreeCAD API\n3. Save with .FCMacro extension\n4. Assign toolbar buttons via Tools > Customize\n5. Macros can automate repetitive tasks and extend functionality.",
                },
            ]
        },
    ]

    # Write dataset
    with open(dataset_path, "w", encoding="utf-8") as f:
        for entry in dataset_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"FreeCAD dataset created at: {dataset_path}")
    print(f"Total entries: {len(dataset_entries)}")


if __name__ == "__main__":
    build_freecad_dataset()
