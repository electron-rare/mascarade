# Dataset refresh brief: components

- generated_at: `2026-03-09T03:53:03`
- dataset_path: `/ai/saisail/mascarade/finetune/datasets/components_chat.jsonl`
- source_mode: `builder_hf`
- row_count: `30`
- quality_status: `passed`
- ids_fixed_in_memory: `0`
- duplicates_removed_during_refresh: `0`

## Web research roots
- [Mouser search help](https://www.mouser.com/help/search/how-to-search-for-products/)
- [Farnell global](https://www.farnell.com/)
- [element14 product search help](https://in.element14.com/help-searching-for-products)
- [DigiKey help](https://www.digikey.com/en/resources/help)
- [Altium documentation](https://www.altium.com/documentation/)
- [EasyEDA libraries management](https://docs.easyeda.com/en/Introduction/Libraries-Management/)

## Hugging Face sources
- [bshada/electronics.stackexchange.com](https://huggingface.co/datasets/bshada/electronics.stackexchange.com)
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)
- [nick007x/eevblog-posts](https://huggingface.co/datasets/nick007x/eevblog-posts)

## Software source roots
- [Mouser search tools](https://www.mouser.com/searchtools/)
- [Farnell datasheets](https://www.farnell.com/italy/datasheets.html)
- [element14](https://www.element14.com/)
- [DigiKey](https://www.digikey.com/)
- [Altium](https://www.altium.com/documentation/)
- [EasyEDA](https://www.easyeda.com/)
- [Octopart](https://octopart.com/)
- [SnapEDA](https://www.snapeda.com/)
- [Ultra Librarian](https://www.ultralibrarian.com/)
- [SamacSys](https://componentsearchengine.com/)
- [LCSC](https://www.lcsc.com/)
- [JLCPCB parts and assembly](https://jlcpcb.com/parts)

## Datasheet and vendor roots
- [Mouser datasheet-oriented search](https://www.mouser.com/help/search/)
- [Farnell datasheets](https://www.farnell.com/italy/datasheets.html)
- [element14 product info and datasheet search](https://in.element14.com/help-searching-for-products)
- [DigiKey datasheets and technical resources](https://www.digikey.com/en/resources/)
- [SnapEDA search](https://www.snapeda.com/)
- [Ultra Librarian search](https://www.ultralibrarian.com/)

## Search queries
- `site:mouser.com part number datasheet parametric search`
- `site:farnell.com datasheets electronic components`
- `site:element14.com component search datasheet availability`
- `site:digikey.com parametric search datasheet availability`
- `site:altium.com documentation component libraries alternates`
- `site:easyeda.com component library lcsc footprint`
- `site:octopart.com parametric component search alternatives`

## Trusted domains
- `mouser.com`
- `farnell.com`
- `element14.com`
- `digikey.com`
- `altium.com`
- `easyeda.com`
- `octopart.com`
- `snapeda.com`
- `ultralibrarian.com`
- `componentsearchengine.com`
- `lcsc.com`
- `jlcpcb.com`

## Legacy ignored by this workflow
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

## Operator checklist
- sample at least 20 refreshed rows and verify technical plausibility
- confirm the newest web findings are represented in prompts/answers
- check duplicates and over-long answers before training
- record any accepted new sources in the research brief before publish
