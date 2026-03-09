# Bench GPU Slots P2000 — 2026-03-08

Contexte:

- machine: `Quadro P2000 5 Go VRAM`
- student: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- lot: `esp32`, `spice`, `pio`
- teacher dataset deja fusionne depuis `finetune/runs/p2000_bench_gpu1_20260308_133320/manifest.json`
- parametres bench:
  - `student_max_samples=64`
  - `epochs=2`
  - `seq_len=256`
  - `tokenize_workers=4`
  - `offline=true`

Reports:

- `slots=1`: `finetune/runs/p2000_train_clean_slots1_20260308_151954/bench.json`
- `slots=2`: `finetune/runs/p2000_train_clean_slots2_20260308_155928/bench.json`

## Resultats

### `gpu_slots=1`

- wall time total: `1984.09 s` (`33m04s`)
- `esp32`: `498.02 s`, loss `1.471890354156494`
- `spice`: `398.02 s`, loss `1.9288729429244995`
- `pio`: `1088.05 s`, loss `1.963248610496521`

### `gpu_slots=2`

- wall time total: `1318.06 s` (`21m58s`)
- `esp32`: `1018.05 s`, loss `1.4718897819519043`
- `spice`: `822.04 s`, loss `1.9289592504501343`
- `pio`: `496.02 s`, loss `1.9634242057800293`

## Lecture

- `slots=2` reduit le temps total de lot de `1984.09 s` a `1318.06 s`
- gain total observe: `666.03 s` (`11m06s`)
- gain relatif observe: environ `33.6 %`
- les losses restent pratiquement identiques entre `1` et `2` slots
- la VRAM observee reste stable autour de `3.07 Go / 5.12 Go` avec `2` trainings simultanes
- aucun `CUDA OOM`, aucun crash trainer sur le bench propre `slots=2`

## Decision

Pour cette machine, garder `2` slots GPU comme profil valide pour les students
de classe `TinyLlama 1.1B` en `seq_len=256` avec lot court (`64` samples ici).

La recommandation operative est:

- conserver le garde-fou VRAM dans `batch_local.py`
- autoriser `2` slots seulement quand le profil student reste dans cette enveloppe memoire
- rester a `1` slot pour les models plus gros ou les contextes plus longs tant qu un bench dedie n a pas valide le profil
- premier modele promu issu de ce bench: `esp32_local_v1`

Ce bench ne generalise pas automatiquement a:

- `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- `Qwen3/Qwen3.5`
- `seq_len > 256`
- datasets significativement plus gros
