# Dataset refresh brief: freecad

- generated_at: `2026-03-09T11:03:07`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/freecad_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `5789`
- quality_status: `warning`
- ids_fixed_in_memory: `6004`
- duplicates_removed_during_refresh: `215`
- research_valid: `True`
- web_roots_count: `30`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [FreeCAD wiki](https://wiki.freecad.org/)
- [FreeCAD project](https://www.freecad.org/)
- [OpenSCAD documentation](https://openscad.org/documentation.html)
- [SOLIDWORKS API Help](https://help.solidworks.com/)
- [Fusion 360 API what's new](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/WhatsNew.htm)

## Hugging Face sources
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)

## Official GitHub sources
- [FreeCAD](https://github.com/FreeCAD/FreeCAD)
- [FreeCAD org](https://github.com/freecad)
- [OpenSCAD](https://github.com/openscad/openscad)
- [CadQuery](https://github.com/CadQuery/cadquery)

## Software source roots
- [FreeCAD project](https://www.freecad.org/)
- [FreeCAD wiki](https://wiki.freecad.org/)
- [OpenSCAD project](https://openscad.org/)
- [CadQuery docs](https://cadquery.readthedocs.io/)
- [Fusion 360 product](https://www.autodesk.com/products/fusion-360/overview)
- [SOLIDWORKS Web Help](https://help.solidworks.com/)

## Specialized forums
- [FreeCAD Forum](https://forum.freecad.org/)
- [CadQuery Community](https://community.cadquery.org/)
- [OpenSCAD Lists](https://lists.openscad.org/)
- [Autodesk Forums](https://forums.autodesk.com/)
- [Onshape Forum](https://forum.onshape.com/)
- [GrabCAD Questions](https://grabcad.com/questions)
- [3D Printing StackExchange](https://3dprinting.stackexchange.com/)
- [LibreCAD Forum](https://forum.librecad.org/)
- [OpenBuilds Forum](https://openbuilds.com/forums/)
- [Maker Forums](https://forum.makerforums.info/)

## Datasheet and vendor roots
- [FreeCAD wiki](https://wiki.freecad.org/)
- [OpenSCAD user manual](https://openscad.org/documentation.html)
- [Fusion 360 API reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/)
- [SOLIDWORKS API Help](https://help.solidworks.com/2024/english/api/sldworksapiprogguide/Welcome.htm)

## Search queries
- `site:wiki.freecad.org PartDesign scripting macro`
- `site:www.freecad.org assembly workbench parametric scripting`
- `site:huggingface.co/datasets freecad cad dataset`
- `site:openscad.org documentation parametric cad`
- `site:cadquery.readthedocs.io cadquery workplane examples`

## Trusted domains
- `wiki.freecad.org`
- `freecad.org`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `24/29`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
