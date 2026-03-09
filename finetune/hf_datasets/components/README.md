---
pretty_name: Mascarade Components Dataset
language:
- en
license: other
task_categories:
- text-generation
task_ids:
- question-answering
tags:
- electronics
- components
- datasheets
- sourcing
- bom
- altium
- easyeda
size_categories:
- n<1K
---

# Mascarade Components Dataset

- Hugging Face repo target: `clemsail/mascarade-components-dataset`
- Canonical file: `components_chat.jsonl`
- Rows: `30`
- Quality status: `passed`
- Quality summary: dataset quality OK
- Duplicates removed during HF packaging: `0`

## Summary

This dataset packages the canonical Mascarade `components` ShareGPT corpus for local fine-tuning and reproducible publication to the Hugging Face Hub.

## Format

Each row is ShareGPT-style JSONL with persistent `id` plus `system` / `human` / `gpt` messages.

## Source roots

### Official docs
- [Mouser search help](https://www.mouser.com/help/search/how-to-search-for-products/)
- [Farnell global](https://www.farnell.com/)
- [element14 product search help](https://in.element14.com/help-searching-for-products)
- [DigiKey help](https://www.digikey.com/en/resources/help)
- [Altium documentation](https://www.altium.com/documentation/)
- [EasyEDA libraries management](https://docs.easyeda.com/en/Introduction/Libraries-Management/)

### Software sources
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

### Datasheet and vendor roots
- [Mouser datasheet-oriented search](https://www.mouser.com/help/search/)
- [Farnell datasheets](https://www.farnell.com/italy/datasheets.html)
- [element14 product info and datasheet search](https://in.element14.com/help-searching-for-products)
- [DigiKey datasheets and technical resources](https://www.digikey.com/en/resources/)
- [SnapEDA search](https://www.snapeda.com/)
- [Ultra Librarian search](https://www.ultralibrarian.com/)

### Upstream Hugging Face datasets
- [bshada/electronics.stackexchange.com](https://huggingface.co/datasets/bshada/electronics.stackexchange.com)
- [STEM-AI-mtl/Electrical-engineering](https://huggingface.co/datasets/STEM-AI-mtl/Electrical-engineering)
- [nick007x/eevblog-posts](https://huggingface.co/datasets/nick007x/eevblog-posts)

## Licensing note

This package aggregates seed-authored material and filtered upstream sources. Review upstream dataset licenses before public redistribution.

Observed license families during packaging:
- `CC-BY-SA-3.0`
- `Apache-2.0`
- `seed-authored`

## Publication commands

```bash
huggingface-cli repo create clemsail/mascarade-components-dataset --type dataset -y
huggingface-cli upload clemsail/mascarade-components-dataset README.md README.md --repo-type dataset
huggingface-cli upload clemsail/mascarade-components-dataset components_chat.jsonl components_chat.jsonl --repo-type dataset
huggingface-cli upload clemsail/mascarade-components-dataset metadata.json metadata.json --repo-type dataset
```

## Quality report

```json
{
  "label": "components hf dataset",
  "mode": "fail",
  "status": "passed",
  "metrics": {
    "row_count": 30,
    "ids_fixed": 0,
    "ids_fixed_ratio": 0.0,
    "unique_system_prompts": 3,
    "unique_user_prompts": 26,
    "duplicate_rows": 0,
    "duplicate_ratio": 0.0,
    "repeated_user_assistant_pairs": 0,
    "repeated_pair_ratio": 0.0,
    "assistant_len_avg": 754.5333333333333,
    "assistant_len_p95": 1609,
    "assistant_len_max": 3240,
    "short_assistant_rows": 0,
    "short_assistant_ratio": 0.0
  },
  "thresholds": {
    "min_rows_fail": 4,
    "recommended_rows_warn": 8,
    "min_unique_users_fail": 4,
    "max_duplicate_ratio_fail": 0.1,
    "max_repeated_pair_ratio_fail": 0.1,
    "max_assistant_p95_fail": 6000,
    "max_assistant_max_fail": 9000,
    "max_assistant_avg_warn": 3500,
    "short_assistant_threshold": 64,
    "max_short_assistant_ratio_warn": 0.25
  },
  "errors": [],
  "warnings": [],
  "would_fail": false
}
```

