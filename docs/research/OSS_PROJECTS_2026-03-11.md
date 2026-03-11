# Open Source Projects for mascarade (2026-03-11)

## Priority Integration
| # | Tool | Stars | Role | Why |
|---|------|-------|------|-----|
| 1 | OpenRLHF | 7k+ | Alignment (SimPO/GRPO) | Ray+vLLM+DeepSpeed, works on RTX 4090 |
| 2 | lm-evaluation-harness | 8k+ | Evaluation | 60+ benchmarks, YAML custom tasks |
| 3 | LLaMA-Factory | 67k | Training orchestration | Config-driven, integrates Unsloth |
| 4 | RLHFlow | 1.4k | Reward model training | Domain-specific alignment |
| 5 | DeepEval | 5k+ | Output quality eval | LLM-as-judge, hallucination detection |

## Also Evaluated (lower priority)
- Axolotl (8k): YAML fine-tuning, alternative to LLaMA-Factory
- LitGPT (13k): redundant with Unsloth
- torchtune (5k): bare PyTorch, less mature multi-node
- NeMo (13k): overkill for current hardware
- MLRun/ZenML: conflicts with existing orchestration
