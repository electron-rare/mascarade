# Finetune Deep Code Audit — subtask-4-4

## 1. Large Script Analysis & Decomposition Proposals

### model_selector.py (1746 lines, 51 functions)
**Responsibilities:** HuggingFace Hub search, model ranking, VRAM estimation, download orchestration, model watch/alerting, validation registry.
**Decomposition proposal:**
- `model_search.py` — Hub queries, caching, filtering (~400 lines)
- `model_ranking.py` — scoring, VRAM estimation, architecture fit (~300 lines)
- `model_watch.py` — watch loop, author patterns, reporting (~250 lines)
- `model_validation.py` — validation registry, integrity checks (~200 lines)
- `model_selector.py` — CLI entry point, `resolve_model()` API, state dir management (~300 lines)

**Issues found:**
- Module-level side effects: `configure_hf_env()`, `_ensure_runtime_tmpdir()`, `_resolve_state_dir()` all run at import time, making testing difficult
- Broad `except Exception` used 21 times — many silently swallow errors (e.g., cache read failures)
- `_resolve_state_dir()` probes filesystem at import — breaks if imported in non-finetune contexts

### batch_local.py (1628 lines, 38 functions)
**Responsibilities:** Multi-domain orchestration, student model selection, distillation subprocess management, training subprocess management, resume logic, manifest writing, quality enforcement.
**Decomposition proposal:**
- `batch_orchestrator.py` — main loop, domain job creation, sequencing (~400 lines)
- `batch_distill.py` — distillation subprocess launching/monitoring (~300 lines)
- `batch_train.py` — training subprocess launching, VRAM checks (~300 lines)
- `batch_resume.py` — manifest loading, resume state reconstruction (~150 lines)
- `batch_local.py` — CLI entry point, arg parsing (~200 lines)

**Issues found:**
- `import torch` at module level — crashes if torch not installed (unlike distill_dataset.py which defers it)
- Resume logic (`load_resume_manifest`) is minimal — no validation of manifest schema
- `DomainJob` dataclass has 18 fields — could be split into distill config + train config

### distill_dataset.py (1324 lines, 41 functions)
**Responsibilities:** Teacher model invocation (API + local HF), prompt generation, response parsing, ShareGPT formatting, concurrency management, quality enforcement, retry logic.
**Decomposition proposal:**
- `teacher_api.py` — endpoint discovery, API calls, provider selection (~300 lines)
- `teacher_local_hf.py` — LocalHFTeacher class, VRAM management (~250 lines)
- `distill_prompts.py` — domain briefs, prompt templates, system prompts (~200 lines)
- `distill_dataset.py` — orchestration, CLI, progress tracking (~400 lines)

**Issues found:**
- `LocalHFTeacher` class does VRAM management but no explicit cleanup/`__del__` — model stays in GPU memory
- Thread safety: `_LOCAL_HF_GENERATE_LOCK` serializes all generation — no benefit from ThreadPoolExecutor for local HF
- 14 broad `except` catches, several swallowing parse errors silently

### dataset_refresh.py (1207 lines, 23 functions)
**Responsibilities:** Dataset refresh orchestration, builder discovery, web research brief generation, research source probing, domain research metadata, quality enforcement.
**Decomposition proposal:**
- `domain_research.py` — DOMAIN_RESEARCH dict, metadata (~400 lines of data)
- `refresh_orchestrator.py` — refresh logic, builder invocation, merging (~400 lines)
- `research_probes.py` — web research probing, brief generation (~200 lines)
- `dataset_refresh.py` — CLI, entry point (~200 lines)

**Issues found:**
- Only 3 `except` clauses in 1207 lines — under-protected compared to other scripts
- `DOMAIN_RESEARCH` dict is ~500 lines of inline data — should be external config (JSON/YAML)

---

## 2. Dataset Builder Consistency (10 builders)

All 10 builders in `finetune/datasets/` follow a consistent pattern:
- **Structure:** SYSTEM_PROMPT → SEED_EXAMPLES list → `build_from_huggingface()` → `main()` → `if __name__`
- **CLI args:** `--with-hf`, `--max-samples`, `--output` (consistent across all)
- **Imports:** `argparse`, `json`, `os`, `re` (all share these)
- **Output format:** ShareGPT JSONL via `write_jsonl` from `sharegpt_utils`

**Inconsistencies found:**
- **Size variance:** 553 lines (DSP) to 1582 lines (PlatformIO) — mostly due to seed example count, not structural
- **Missing builder:** `components` domain is in SUPPORTED_DOMAINS (batch_local.py, distill_dataset.py, dataset_refresh.py) but has NO builder script — will silently fall back to seed bootstrap only
- **KiCad has duplicate `if __name__` block** at line 531 (inside a string literal in seed data) — not a bug but confusing for tooling
- **Spice has extra `build_from_external()`** function not present in other builders — inconsistent interface

### Domain list consistency:
| File | Domain count | Has `components`? |
|------|-------------|-------------------|
| batch_local.py SUPPORTED_DOMAINS | 11 | ✅ |
| distill_dataset.py DEFAULT_DOMAINS | 11 | ✅ |
| dataset_refresh.py SUPPORTED_DOMAINS | 11 | ✅ |
| Actual builders in datasets/ | **10** | ❌ Missing |

---

## 3. Error Handling Gaps

| Script | except clauses | Broad catches | Key gaps |
|--------|---------------|---------------|----------|
| model_selector.py | 21 | ~15 broad | Silent cache/download failures |
| batch_local.py | 8 | ~5 broad | No subprocess timeout handling |
| distill_dataset.py | 14 | ~10 broad | Silent JSON parse failures in teacher responses |
| dataset_refresh.py | 3 | ~2 broad | Under-protected subprocess calls |

**Specific gaps:**
- **batch_local.py:** Subprocess calls to `distill_dataset.py` and `run_local.py` have no timeout — can hang forever
- **distill_dataset.py:** `LocalHFTeacher._load_model()` catches `TypeError` and flash_attention errors but not OOM
- **model_selector.py:** Network errors during Hub search are caught but retries are not exponential
- **dataset_refresh.py:** Builder subprocess errors only logged, not propagated — silent partial failures

---

## 4. VRAM Management

VRAM management is spread across 13 files. Key patterns:
- **model_selector.py:** Estimates VRAM from model config (param count × dtype size + overhead) — heuristic only
- **auto_policy.py:** `detect_machine_profile()` reads `torch.cuda.get_device_properties()` for VRAM budget
- **distill_dataset.py:** LocalHFTeacher loads with `device_map="auto"` — relies on accelerate for VRAM splitting
- **train_local.py / run_local.py:** Use gradient checkpointing, configurable batch size for VRAM control
- **No explicit VRAM monitoring during training** — OOM errors crash the process with no graceful recovery

---

## 5. Batch/Resume Logic

- **batch_local.py** `load_resume_manifest()` reads a manifest.json to reconstruct state
- Resume skips domains whose distillation output already exists (file existence check only)
- **No checkpointing within a domain** — if distillation crashes mid-domain, all progress for that domain is lost
- **No training resume** — if training crashes, the entire training run restarts from scratch
- `distill_dataset.py` does have incremental append (writes rows as they complete) — provides some crash resilience

---

## 6. Test Coverage

**Zero test files found** for the entire finetune/ directory. No `tests/` folder, no `test_*.py` files.

**Priority test targets:**
1. `sharegpt_utils.py` — pure functions, easy to unit test, used everywhere
2. `model_selector.py` — scoring/ranking logic is testable in isolation
3. `dataset_quality.py` — validation logic should be tested
4. `batch_local.py` — resume manifest parsing needs tests
5. Dataset builders — output format validation

---

## Summary of Actionable Findings

| Finding | Severity | Effort |
|---------|----------|--------|
| Missing `components` dataset builder | Medium | Low |
| Zero test coverage | High | High |
| Module-level side effects in model_selector.py | Medium | Medium |
| `import torch` at top of batch_local.py | Low | Low |
| No subprocess timeouts in batch orchestration | Medium | Low |
| No VRAM OOM recovery | Medium | High |
| No mid-domain checkpointing for distillation | Low | Medium |
| DOMAIN_RESEARCH inline data blob | Low | Medium |
| 4 large scripts need decomposition | Low | High |
