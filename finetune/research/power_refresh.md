# Dataset refresh brief: power

- generated_at: `2026-03-09T12:09:35`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/power_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `3260`
- quality_status: `warning`
- ids_fixed_in_memory: `3267`
- duplicates_removed_during_refresh: `7`
- research_valid: `True`
- web_roots_count: `19`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [TI power management docs](https://www.ti.com/power-management/overview.html)
- [Analog Devices technical articles](https://www.analog.com/en/technical-articles.html)

## Hugging Face sources
- [ksabeh/electronics-dataset](https://huggingface.co/datasets/ksabeh/electronics-dataset)
- [bshada/electronics.stackexchange.com](https://huggingface.co/datasets/bshada/electronics.stackexchange.com)
- [nick007x/eevblog-posts](https://huggingface.co/datasets/nick007x/eevblog-posts)

## Software source roots
- [ADI Power Studio](https://www.analog.com/en/resources/evaluation-hardware-and-software/embedded-development-software/power-studio-designer.html)
- [TI power management hub](https://www.ti.com/power-management/overview.html)

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
- [Analog Devices technical articles](https://www.analog.com/en/technical-articles.html)
- [TI power management documentation](https://www.ti.com/power-management/overview.html)

## Search queries
- `site:ti.com current mode control compensation application note`
- `site:analog.com buck converter loop stability article`
- `site:huggingface.co/datasets electronics power converter dataset`

## Trusted domains
- `ti.com`
- `analog.com`
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
