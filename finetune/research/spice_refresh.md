# Dataset refresh brief: spice

- generated_at: `2026-03-09T12:09:52`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/spice_chat.jsonl`
- source_mode: `full_dataset_sync`
- row_count: `8421`
- quality_status: `warning`
- ids_fixed_in_memory: `8421`
- duplicates_removed_during_refresh: `0`
- research_valid: `True`
- web_roots_count: `17`
- forum_count: `10`
- quality_score: `9`
- web_probe_status: `partial`

## Web research roots
- [ngspice documentation](https://ngspice.sourceforge.io/docs.html)
- [LTspice overview](https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html)

## Hugging Face sources
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)

## Official GitHub sources
- [ngspice](https://github.com/ngspice/ngspice)

## Software source roots
- [ngspice upstream](https://ngspice.sourceforge.io/)
- [LTspice download and models](https://www.analog.com/en/resources/simulation-models/spice-models.html)

## Specialized forums
- [ngspice Discussions](https://sourceforge.net/p/ngspice/discussion/)
- [LTspice Groups](https://groups.io/g/LTspice)
- [Cadence Community](https://community.cadence.com/)
- [Analog Devices EngineerZone](https://ez.analog.com/)
- [TI E2E](https://e2e.ti.com/)
- [All About Circuits Forum](https://forum.allaboutcircuits.com/)
- [EEVblog Forum](https://www.eevblog.com/forum/)
- [Electronics StackExchange SPICE](https://electronics.stackexchange.com/questions/tagged/spice)
- [Electronics StackExchange LTspice](https://electronics.stackexchange.com/questions/tagged/ltspice)
- [PSMA Technical Forums](https://psma.com/technical-forums/)

## Datasheet and vendor roots
- [Analog Devices LTspice macromodels](https://www.analog.com/en/resources/simulation-models/spice-models.html)

## Search queries
- `site:ngspice.sourceforge.io ngspice convergence transient noise`
- `site:analog.com ltspice switch-mode power simulation`
- `site:huggingface.co/datasets electrical engineering spice dataset`

## Trusted domains
- `ngspice.sourceforge.io`
- `analog.com`
- `huggingface.co`

## Live web probe
- status: `partial`
- reachable: `7/16`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
