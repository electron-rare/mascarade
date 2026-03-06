# Fine-Tuning Cheatsheet

Date de reference: 2026-03-06

Version courte du document complet:

- voir `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md` pour le detail

## 1. Regle simple

Pour cette machine:

- ne vise pas un gros fine-tuning dense
- vise un petit student local
- utilise un gros teacher pour generer de bonnes donnees
- fais du SFT en LoRA/QLoRA

## 2. Quel chemin choisir

| Si ton besoin est... | Fais ca |
|---|---|
| format, style, procedure, ton | SFT |
| transferer la qualite d un gros modele vers un petit | distillation + SFT |
| choisir entre plusieurs bonnes ou mauvaises reponses | DPO / ORPO / KTO |
| optimiser une tache objectivement notee | GRPO / RFT |
| injecter beaucoup de savoir brut | continued pretraining |
| entrainer un gros modele serieusement | cloud / managed |

## 3. Ce qui est realiste ici

Machine actuelle:

- GPU Quadro P2000
- environ 5 Go de VRAM

Donc:

- 1B a 1.5B: oui
- 3B: parfois, en mode serre
- 7B+: pas un workflow local confortable
- full fine-tuning: non

## 4. Workflow recommande

1. definir un petit eval set
2. distiller avec un gros teacher
3. fusionner source + distillation
4. fine-tuner un petit student local
5. evaluer avant/apres

## 5. Commandes utiles

Check environnement:

```bash
source venv_tuning/bin/activate
python test_environment.py
```

Fine-tuning local simple:

```bash
python finetune/run_local.py stm32 --device auto --max-samples 128 --epochs 1
```

Distillation seule:

```bash
python finetune/distill_dataset.py stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2
```

Pipeline complet teacher -> student:

```bash
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --device gpu \
  --epochs 1
```

## 6. Reglage de depart recommande

Teacher:

- provider `mistral` via Mascarade

Student:

- `TinyLlama/TinyLlama-1.1B-Chat-v1.0`

Hyperparametres de depart:

- `max-source-samples=32`
- `samples-per-source=2`
- `epochs=1`
- `seq-len=256`

Puis monter doucement:

- `max-source-samples=64`
- `epochs=2`

## 7. Ce qu il ne faut pas faire trop tot

- lancer DPO avant un bon SFT
- lancer du RL sans grader robuste
- viser 7B+ local sur cette carte
- remplacer un eval set par une impression subjective
- empiler des methodes avant d avoir valide le baseline

## 8. Ordre de priorite

Avant de complexifier:

1. meilleur eval set
2. meilleur dataset
3. meilleure distillation
4. meilleur SFT
5. ensuite seulement preference tuning ou RL

## 9. Lecture suivante

- recap complet: `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`
- doc pipeline local: `finetune/README.md`
