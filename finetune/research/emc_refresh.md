# Dataset refresh brief: emc

- generated_at: `2026-03-09T12:09:00`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/emc_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `3356`
- quality_status: `warning`
- ids_fixed_in_memory: `3360`
- duplicates_removed_during_refresh: `4`
- research_valid: `True`
- web_roots_count: `19`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [TI EMC overview](https://www.ti.com/interface/emc-overview.html)
- [Infineon EMC resources](https://www.infineon.com/cms/en/design-support/)

## Hugging Face sources
- [bshada/electronics.stackexchange.com](https://huggingface.co/datasets/bshada/electronics.stackexchange.com)
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)
- [nick007x/eevblog-posts](https://huggingface.co/datasets/nick007x/eevblog-posts)

## Software source roots
- [TI EMC overview](https://www.ti.com/interface/emc-overview.html)
- [Infineon design support](https://www.infineon.com/cms/en/design-support/)

## Specialized forums
- [Electronics StackExchange](https://electronics.stackexchange.com/)
- [All About Circuits Forum](https://forum.allaboutcircuits.com/)
- [EEVblog Forum](https://www.eevblog.com/forum/)
- [DigiKey TechForum](https://forum.digikey.com/)
- [element14 Community](https://community.element14.com/)
- [TI E2E](https://e2e.ti.com/)
- [Analog Devices EngineerZone](https://ez.analog.com/)
- [Infineon Community](https://community.infineon.com/)
- [NXP Community](https://community.nxp.com/)
- [Arduino Forum](https://forum.arduino.cc/)

## Datasheet and vendor roots
- [TI EMC overview](https://www.ti.com/interface/emc-overview.html)
- [Infineon design support](https://www.infineon.com/cms/en/design-support/)

## Search queries
- `site:ti.com emc layout esd protection application note`
- `site:infineon.com emi filter pcb layout note`
- `site:huggingface.co/datasets electronics emc emi dataset`

## Trusted domains
- `ti.com`
- `infineon.com`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `8/16`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
