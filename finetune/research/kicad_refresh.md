# Dataset refresh brief: kicad

- generated_at: `2026-03-09T12:08:43`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/kicad_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `2644`
- quality_status: `warning`
- ids_fixed_in_memory: `2645`
- duplicates_removed_during_refresh: `1`
- research_valid: `True`
- web_roots_count: `26`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [KiCad documentation](https://docs.kicad.org/)
- [KiCad forum](https://forum.kicad.info/)
- [Altium documentation](https://www.altium.com/documentation/)
- [EasyEDA docs](https://docs.easyeda.com/en/)

## Hugging Face sources
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)
- [bshada/electronics.stackexchange.com](https://huggingface.co/datasets/bshada/electronics.stackexchange.com)
- [ksabeh/electronics-dataset](https://huggingface.co/datasets/ksabeh/electronics-dataset)

## Official GitHub sources
- [KiCad GitHub org](https://github.com/KiCad)
- [KiCad source mirror](https://github.com/KiCad/kicad-source-mirror)

## Software source roots
- [KiCad source download](https://www.kicad.org/download/source/)
- [KiCad developer docs](https://dev-docs.kicad.org/)
- [Altium Designer docs](https://www.altium.com/documentation/)
- [EasyEDA product](https://www.easyeda.com/)

## Specialized forums
- [KiCad.info Forums](https://forum.kicad.info/)
- [KiCad Community Forums](https://www.kicad.org/community/forums/)
- [EEVblog Forum](https://www.eevblog.com/forum/)
- [Electronics StackExchange PCB Design](https://electronics.stackexchange.com/questions/tagged/pcb-design)
- [EDAboard](https://www.edaboard.com/)
- [EasyEDA Forum](https://easyeda.com/forum/)
- [Altium Forum](https://forum.live.altium.com/)
- [Arduino Forum](https://forum.arduino.cc/)
- [All About Circuits Forum](https://forum.allaboutcircuits.com/)
- [element14 Community](https://community.element14.com/)

## Datasheet and vendor roots
- [KiCad library conventions](https://klc.kicad.org/)
- [KiCad libraries](https://kicad.github.io/)
- [EasyEDA libraries management](https://docs.easyeda.com/en/Introduction/Libraries-Management/)

## Search queries
- `site:docs.kicad.org differential pair design rules`
- `site:forum.kicad.info footprint courtyard ipc`
- `site:huggingface.co/datasets kicad pcb dataset`

## Trusted domains
- `docs.kicad.org`
- `forum.kicad.info`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `19/23`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
