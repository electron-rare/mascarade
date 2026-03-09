# Dataset Refresh Workflow

Canonical workflow for refreshing fine-tuning datasets before distillation or local training.

## Policy

1. Prefer the sibling full dataset repo when present:
   - `/ai/saisail/mascarade-datasets/<domain>_chat.jsonl`
2. Otherwise rebuild with the active canonical builder:
   - `finetune/datasets/build_<domain>_dataset.py`
3. After refresh:
   - validate ShareGPT structure
   - apply the dataset quality gate
   - dedupe the final refreshed dataset and record `duplicates_removed`
   - write a web-research brief in `finetune/research/`
   - run a live HTTP probe of the registered web sources and persist the result in `finetune/research_probes/`
   - validate that the brief contains real web source roots, search queries and trusted domains before dataset use in distillation/training

The canonical workflow now blocks refresh if web research is missing or incomplete.
Override is intentionally explicit only via `MASCARADE_ALLOW_SKIP_WEB_RESEARCH=1`.
It uses a research quality gate, not a forum-count gate.
The canonical source registry now lives in:
- `finetune/research_sources/domains/<domain>.json`

## Operator commands

```bash
./scripts/sync_research_sources.sh
python finetune/dataset_refresh.py stm32 platformio components --with-hf
python finetune/run_local.py stm32 --refresh-dataset --refresh-with-hf --device gpu
python finetune/batch_local.py stm32 spice pio --refresh-datasets --refresh-with-hf
```

## Research brief outputs

Per domain, the refresh writes:
- `finetune/research/<domain>_refresh.md`
- `finetune/research/<domain>_refresh.json`

Each brief records:
- refresh timestamp
- dataset source mode (`full_dataset_sync`, `builder_seed`, `builder_hf`, ...)
- current row count
- dataset quality status
- duplicates removed during refresh
- authoritative source roots
- specialized forum/community roots
- official GitHub roots when they exist
- software source roots
- datasheet / vendor roots
- Hugging Face dataset roots
- query templates for associated web research
- live probe status and reachable source count
- a `research_validation` block used as a training gate
  - including `forum_count`, `quality_score`, and domain-specific `minimum_web_roots`

Canonical forum/community roots per domain are listed in:
- `docs/DATASET_DOMAIN_FORUMS.md`

The machine-readable source-of-truth used by `dataset_refresh.py` is:
- `finetune/research_sources/domains/*.json`

The live probe artifacts used by the workflow are:
- `finetune/research_probes/*.json`

## Retired legacy builders

These historical builders are no longer part of the canonical workflow:
- `finetune/build_components_dataset.py`
- `finetune/build_freecad_dataset.py`

The supported path is now only:
- `finetune/datasets/build_<domain>_dataset.py`
