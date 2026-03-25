# Training Workspace

Ce dossier sert a preparer et evaluer un cycle de fine-tuning sans melanger les artefacts runtime.

## Structure

- `data/`: datasets JSONL (train/val/eval)
- `scripts/`: outils de validation et baseline eval
- `output/`: resultats d'eval (non commit)

## Format JSONL

Chaque ligne est un objet JSON:

```json
{
  "id": "ex-001",
  "messages": [
    {"role": "system", "content": "You are a concise assistant."},
    {"role": "user", "content": "Explique le pattern Strategy en 2 phrases."}
  ],
  "expected": "Le pattern Strategy encapsule des algorithmes interchangeables..."
}
```

- `id` requis
- `messages` requis (liste de messages role/content)
- `expected` recommande pour scoring

## Commandes

Readiness providers (essais):

```bash
bash training/scripts/check_provider_readiness.sh
```

Validation:

```bash
python3 training/scripts/validate_dataset.py training/data/eval.sample.jsonl
```

Baseline eval (dry-run):

```bash
python3 training/scripts/run_baseline_eval.py \
  --eval training/data/eval.sample.jsonl \
  --out training/output/baseline_results.sample.jsonl \
  --summary training/output/baseline_summary.sample.md \
  --dry-run
```

Baseline eval reelle (Mascarade API):

```bash
python3 training/scripts/run_baseline_eval.py \
  --eval training/data/eval.jsonl \
  --out training/output/baseline_results.jsonl \
  --summary training/output/baseline_summary.md \
  --api-url http://localhost:3100 \
  --providers bedrock,openai,mistral,google,claude,huggingface \
  --api-key "$MASCARADE_API_KEY"
```

Quick compare all providers en 1 commande:

```bash
bash training/scripts/quick_compare_all.sh
```

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
