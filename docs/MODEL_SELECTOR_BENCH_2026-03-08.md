# Model Selector Bench 2026-03-08

Machine mesuree:

- GPU: `Quadro P2000`
- VRAM totale: `5120 MiB`

Comparaison realisee entre:

- choix automatique courant via `finetune/selected_model.json`
- choix manuel historique du pipeline local

## Resultat

| Mode | Modele | VRAM estimee | HumanEval | Score selector | Cache local |
|---|---|---:|---:|---:|---|
| auto | `Qwen/Qwen2.5-Coder-3B-Instruct` | `3.01G` | `76.2` | `78.4` | non |
| manuel | `Qwen/Qwen2.5-Coder-1.5B-Instruct` | `2.00G` | `70.7` | `70.8` | oui |

## Lecture

- les deux modeles restent dans l enveloppe heuristique des `5 Go` de la P2000
- le `3B` gagne en qualite theorique et en score de selection
- le `1.5B` garde un avantage operateur fort: il est deja en cache local

## Decision pratique

- online / normal: preferer `Qwen/Qwen2.5-Coder-3B-Instruct`
- offline / reprise rapide / machine fragile: garder `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- override explicite possible a tout moment via `--student-model`

## Commandes utilisees

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python finetune/model_selector.py --auto --json
cat finetune/selected_model.json
```

## Conclusion

Le branchement de `selected_model.json` dans `batch_local.py` est pertinent sur cette machine.

Le meilleur compromis automatique courant est le `3B`, mais le `1.5B` doit rester le fallback operateur quand la disponibilite du cache ou la robustesse de run priment sur la qualite brute.
