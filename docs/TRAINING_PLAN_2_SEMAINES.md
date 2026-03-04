# PLAN TRAINING 2 SEMAINES (MASCARADE)

Date de reference: 2026-03-04
Objectif: lancer un cycle de fine-tuning evalue et decisionnel sans casser la prod.
Priorite initiale: AWS Bedrock.

## Cible

- Cas d'usage: 1 tache metier critique (support, extraction, generation, etc.)
- Providers compares:
  - AWS Bedrock custom model (priorite sprint 1)
  - OpenAI fine-tuning (benchmark 1)
  - Mistral fine-tuning (benchmark 2)
  - Vertex AI tuning (benchmark 3 si besoin)
  - Hugging Face Inference (benchmark rapidite/cout local-open)
- Serveur d'inference cible: Mascarade (API + core) + Langfuse pour traces

## Livrables attendus

- Dataset versionne:
  - `training/data/train.jsonl`
  - `training/data/val.jsonl`
  - `training/data/eval.jsonl`
- Baseline multi-provider avant tuning:
  - `training/output/baseline_results.jsonl`
  - `training/output/baseline_summary.md`
- Decision memo go/no-go provider
- Runbook de deploiement du modele tune

## Planning (2 semaines)

### Semaine 1

J1:
- Verifier service API Mascarade disponible.
- Definir schema de dataset et labels.
- Creer un premier lot de 30-50 exemples.

J2:
- Etendre train a 100-200 exemples.
- Construire eval set de 30-50 exemples hors train.
- Lancer validation dataset:
  - `python3 training/scripts/validate_dataset.py training/data/train.jsonl`
  - `python3 training/scripts/validate_dataset.py training/data/eval.jsonl`

J3:
- Lancer baseline avec modeles non tunes:
  - `python3 training/scripts/run_baseline_eval.py --eval training/data/eval.jsonl --out training/output/baseline_results.jsonl --summary training/output/baseline_summary.md`
- Capturer latence, reussite, exact-match.

J4:
- Nettoyage dataset selon erreurs top-10.
- Ajouter exemples difficiles / edge cases.

J5:
- Sprint 1 fige sur Bedrock:
  - critere principal: qualite sur eval set
  - critere secondaire: cout + latence + simplicite ops
  - si score insuffisant, fallback benchmark OpenAI puis Mistral

### Semaine 2

J6-J7:
- Lancer fine-tuning Bedrock.
- En parallele optionnel: 1 benchmark court OpenAI pour reference cout/qualite.
- Versionner hyperparams + dataset hash.

J8:
- Eval post-tuning sur `eval.jsonl` avec le meme script baseline.
- Comparer pre/post (exact-match, score de longueur, latence).

J9:
- Test integration Mascarade:
  - routing explicite vers modele tune
  - fallback vers modele foundation

J10:
- Go/no-go prod.
- Deploiement canary (trafic partiel), suivi Langfuse.

## Criteres de succes minimum

- +10 points exact-match vs baseline sur eval set
- Aucune regression critique sur 20 prompts metier "must-pass"
- Cout par reponse acceptable par rapport a l'objectif metier

## Execution immediate (ce qui est deja en place)

Le dossier `training/` contient:
- templates dataset
- validation structure JSONL
- baseline evaluator multi-provider via `/api/agents/send`

Commande rapide:

```bash
python3 training/scripts/validate_dataset.py training/data/eval.sample.jsonl
python3 training/scripts/run_baseline_eval.py \
  --eval training/data/eval.sample.jsonl \
  --out training/output/baseline_results.sample.jsonl \
  --summary training/output/baseline_summary.sample.md \
  --dry-run
```
