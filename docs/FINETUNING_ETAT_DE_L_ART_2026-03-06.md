# Fine-Tuning, Distillation Et Post-Training

Date de reference: 2026-03-06

Ce document resume:

- les etapes utiles pour adapter un modele
- les options deja disponibles dans ce repo
- ce qui est realiste sur cette machine
- l'etat de l'art pratique verifie au 6 mars 2026

Version courte:

- `docs/FINETUNING_CHEATSHEET_2026-03-06.md`

## 1. Resume Executif

Pour cette machine, la strategie recommandee est:

1. definir un eval set propre
2. produire ou enrichir un dataset via distillation teacher -> student
3. faire un SFT local en LoRA/QLoRA sur un petit modele
4. evaluer avant/apres
5. seulement ensuite envisager preference tuning ou RL

En pratique, sur la Quadro P2000 5 Go:

- oui: distillation, SFT local, LoRA, QLoRA, petits students 1B a 1.5B
- parfois: 3B en mode serre
- non ou peu realiste: full fine-tuning dense, gros 7B+ confortables, RL serieux local

## 2. Decision Tree

### Cas A: Tu veux un modele local utile vite

Choix recommande:

- teacher grand modele
- generation de dataset specialise
- student petit modele
- LoRA/QLoRA local

C est exactement le workflow le plus pragmatique pour cette machine.

### Cas B: Tu veux corriger le style, le format, la structure de sortie

Choix recommande:

- SFT seulement
- 50 a 500 bons exemples peuvent deja suffire

### Cas C: Tu veux mieux aligner le modele sur des preferences

Choix recommande:

- DPO, ORPO ou KTO
- uniquement si tu as deja un bon SFT de base

### Cas D: Tu veux pousser du raisonnement expert avec une metrique verifiable

Choix recommande:

- RL type GRPO ou RFT
- a reserver aux cas ou tu disposes d un grader fiable
- plutot cloud ou multi-GPU que local ici

### Cas E: Tu veux injecter du savoir de domaine brut

Choix recommande:

- continued pretraining / domain adaptation
- utile si ton probleme est surtout "le modele ne connait pas assez le domaine"
- beaucoup plus lourd qu un simple SFT

## 3. Etat De L Art Pratique En 2026

### 3.1 Ce que montrent les docs officielles aujourd hui

Au 2026-03-06, le paysage pratique n est pas "une methode magique unique". Les piles majeures exposent plutot un continuum:

- SFT comme base standard
- preference tuning au dessus du SFT
- RL / RFT quand on a un grader ou une reward robuste
- PEFT / QLoRA pour reduire le cout memoire
- cloud managed quand on veut monter en taille, en modalites ou en parallelisme

Ce point est verifie dans les docs officielles actuelles:

- Hugging Face TRL documente SFT, DPO et GRPO; KTO, ORPO et GKD sont exposes dans les sections experimentales
- OpenAI documente SFT, DPO et reinforcement fine-tuning
- Vertex AI documente supervised tuning, preference tuning, checkpoints et continuous tuning sur Gemini
- Amazon Bedrock documente SFT et reinforcement fine-tuning; sa boucle RFT s appuie explicitement sur GRPO

Ce document ne pretend donc pas classer une "meilleure methode absolue". Il resume la bonne methode selon:

- le type de signal disponible
- le budget compute
- la qualite du dataset
- la presence ou non d un grader automatique

### 3.2 Avant de fine-tuner

Toujours verifier d abord si le probleme se corrige avec:

- meilleur prompt
- meilleure structure de sortie
- prompt caching
- RAG
- routing entre plusieurs modeles

En 2026, beaucoup de cas "fine-tuning" sont en fait mieux servis par:

- un meilleur eval set
- un meilleur prompt
- du distillation de grand modele
- un petit adapter au lieu d un gros entrainement

### 3.3 SFT reste la base

Le SFT reste la couche standard de post-training:

- simple a mettre en place
- efficace pour style, format, comportement, procedures de domaine
- compatible avec PEFT et QLoRA

Pour un usage local ou budget serre, c est la premiere methode a faire.

En 2026, c est toujours le point d entree le plus robuste quand:

- tu veux changer le comportement
- tu veux imposer un format de sortie
- tu veux specialiser un petit modele

### 3.4 Distillation est la meilleure option budget/qualite

La distillation teacher -> student est une technique cle:

- un grand modele sert de professeur
- on capture des demonstrations de haute qualite
- on SFT un modele plus petit sur ces exemples

En pratique, c est souvent le meilleur rapport:

- cout
- vitesse d inference
- qualite specialisee

En pratique recente, on voit aussi monter la distillation plus "active":

- teacher generateur de demonstrations
- knowledge distillation plus structuree
- on-policy distillation / GKD quand on veut mieux coller a la distribution reelle du student

Mais pour ce repo, la version la plus utile reste la plus simple:

- gros teacher
- dataset propre
- petit student local
- SFT/QLoRA

### 3.5 Preference tuning: DPO, ORPO, KTO

Quand le SFT fonctionne deja mais pas assez bien sur le "bon choix" entre plusieurs reponses:

- DPO: le standard le plus connu
- ORPO: variante plus simple et souvent pratique
- KTO: utile quand on a des signaux de preference plus faibles ou implicites

Ca demande un dataset de preferences, pas seulement des demos.

Ce qu il faut retenir aujourd hui:

- DPO est bien adapte aux choix subjectifs entre deux sorties
- ORPO est interessant quand on veut eviter une phase separee avec reference model
- KTO reste pertinent quand on a des signaux desirable / undesirable plus simples que des paires strictes

### 3.6 RL moderne: GRPO, RFT, RLVR

Pour les taches ou on peut noter objectivement une reponse:

- code
- maths
- extraction structuree
- questions a verifications automatiques

les methodes de type:

- GRPO
- reinforcement fine-tuning
- RL with verifiable rewards

sont aujourd hui importantes.

Mais ce n est pas le bon premier levier sur une petite machine locale. Le vrai prerequis est un grader robuste.

Le point cle n est pas "faire du RL" mais:

- definir une reward utile
- la calculer vite
- verifier qu elle ne pousse pas vers des comportements parasites

Sans cela, RL devient vite plus fragile qu un simple SFT bien prepare.

### 3.7 LoRA, QLoRA et variantes

Pour le local, les variantes PEFT restent dominantes:

- LoRA
- QLoRA
- DoRA
- OLoRA
- EVA
- AdaLoRA

En 2026, la recommandation pratique reste:

- commencer par LoRA ou QLoRA
- n explorer DoRA, EVA, OLoRA que si le baseline est deja propre

Point pratique actuel:

- LoRA reste la base simple
- QLoRA reste la base memoire/prix
- DoRA peut aider a bas rank, mais avec plus d overhead
- AdaLoRA, EVA, OLoRA sont des optimisations de second tour, pas le premier choix

### 3.8 Full fine-tuning et FSDP2

Le full fine-tuning existe toujours, mais il est reserve a:

- besoins tres ambitieux
- gros clusters
- multi-GPU
- gros budgets

FSDP2 est aujourd hui la voie PyTorch propre pour entrainer plus gros en distribue.

### 3.9 Multimodal devient normal cote managed

En 2026, les plateformes managed ne limitent plus le tuning au texte seul:

- OpenAI expose aussi le vision fine-tuning
- Vertex documente du supervised tuning texte, image, document, audio et video pour Gemini
- Bedrock supporte aussi plusieurs familles de modeles personnalises selon la tache

Pour ce repo en revanche, il faut rester pragmatique:

- notre pipeline local actuel est text/chat
- le premier objectif reste un bon student technique local

## 4. Ce Qui Est Realiste Sur Cette Machine

Contrainte locale actuelle:

- GPU: Quadro P2000
- VRAM utile: environ 5 Go

Consequences:

- TinyLlama 1.1B: oui
- petits Qwen 0.5B a 1.5B: oui selon config
- 3B: possible mais serre
- 7B: tres contraint, pas un flux de travail confortable
- 13B+: non

Choix recommande ici:

- teacher externe ou cloud
- student 1B a 1.5B
- QLoRA 4-bit
- sequences courtes a moyennes
- eval systematique

## 5. Options Disponibles Dans Ce Repo

### 5.1 Check d environnement

Commande:

```bash
source venv_tuning/bin/activate
python test_environment.py
```

But:

- verifier Python, torch, CUDA
- verifier les datasets locaux
- verifier le chemin CPU et GPU

### 5.2 Fine-tuning local simple

Point d entree:

```bash
python finetune/run_local.py <domain>
```

Commandes utiles:

```bash
python finetune/run_local.py stm32 --device auto --max-samples 128 --epochs 1
python finetune/run_local.py kicad --device cpu --model gpt2 --max-samples 64
python finetune/run_local.py stm32 --device gpu --model TinyLlama/TinyLlama-1.1B-Chat-v1.0
```

Options principales:

- `--device {auto,gpu,cpu}`: choix du device
- `--model`: override du modele de base
- `--dataset-path`: dataset ShareGPT JSONL derive
- `--output-dir`: dossier de sortie
- `--seq-len`
- `--epochs`
- `--max-samples`
- `--tokenize-workers`: workers CPU pour la tokenization, `0` = auto
- `--eval`: uniquement chemin GPU
- `--offline`: forcer le cache Hugging Face local
- `--verbose`: plus de detail sur le launcher et le trainer
- `--quiet`: sortie minimale, sans progress bars trainer

### 5.3 Distillation seule

Point d entree:

```bash
python finetune/distill_dataset.py <domain>
```

Commande typique:

```bash
python finetune/distill_dataset.py stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --verbose
```

Options principales:

- `--source-dataset`: dataset ShareGPT source
- `--out`: dataset distille
- `--report-path`: rapport JSON
- `--api-url`: URL Mascarade core/API
- `--api-key`: bearer token si necessaire
- `--teacher-provider`
- `--teacher-model`
- `--strategy`
- `--temperature`
- `--max-tokens`
- `--timeout`
- `--max-source-samples`
- `--samples-per-source`
- `--concurrency`: appels teacher en parallele, `0` = auto
- `--seed`
- `--sleep-ms`
- `--teacher-system-path`
- `--dry-run`
- `--verbose`
- `--quiet`

### 5.4 Pipeline complet distillation -> merge -> train

Point d entree:

```bash
python finetune/distill_and_train.py <domain>
```

Wrapper shell:

```bash
./scripts/distill_and_train.sh <domain> ...
```

Commande recommandee sur cette machine:

```bash
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --device gpu \
  --epochs 1 \
  --train-output-dir /tmp/stm32_student_gpu
```

Ce pipeline:

1. lit le dataset source
2. appelle le teacher
3. ecrit le dataset distille
4. fusionne source + distillation avec deduplication
5. lance le fine-tuning local du student

Options principales en plus:

- `--distilled-out`
- `--merged-out`
- `--student-model`
- `--student-max-samples`
- `--train-output-dir`
- `--tokenize-workers`
- `--distill-concurrency`
- `--skip-train`
- `--skip-distill`
- `--dry-run`
- `--verbose`
- `--quiet`

### 5.5 Scripts cloud ou managed deja presents

Dans le repo il existe aussi:

- `finetune/bedrock_finetune.py`
- `scripts/vertex_finetune.py`
- `scripts/mistral_studio_finetune.py`

Ces chemins sont pertinents si:

- tu veux entrainer un modele plus gros
- tu veux eviter la limite VRAM locale
- tu veux du fine-tuning managed

## 6. Workflow Recommande Pour Ce Projet

### Niveau 1: flux le plus pragmatique

1. construire un petit eval set de reference
2. choisir un domaine
3. lancer la distillation teacher -> student
4. faire un SFT local
5. mesurer avant/apres

Commande type:

```bash
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider mistral \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --device gpu \
  --epochs 1
```

### Niveau 2: si le SFT ne suffit pas

Ensuite seulement:

- construire un dataset de preferences
- tester DPO ou ORPO

### Niveau 3: si tu as un grader robuste

Ensuite seulement:

- GRPO
- RFT
- RLVR

## 7. Choisir La Bonne Methode

### 7.0 Tableau de choix rapide

| Besoin principal | Signal disponible | Methode recommandee |
|---|---|---|
| Changer le format, le style, la procedure | demos correctes | SFT |
| Transferer la qualite d un gros modele vers un petit | teacher fort | distillation + SFT |
| Apprendre a preferer une meilleure reponse | paires chosen/rejected | DPO |
| Aligner sans reference model lourd | preferences | ORPO |
| Apprendre avec desirable / undesirable plus faibles | labels implicites ou unpaired | KTO |
| Optimiser une tache objectivement notee | grader / reward fiable | GRPO ou RFT |
| Injecter de la connaissance de domaine brute | gros corpus texte | continued pretraining |
| Changer largement le modele de base | gros budget multi-GPU | full fine-tuning |

### Prompt / RAG

A utiliser si:

- le probleme est surtout de contexte
- le savoir change souvent
- tu ne veux pas toucher aux poids

### SFT

A utiliser si:

- tu veux apprendre un comportement
- tu veux un style de sortie
- tu veux un format ou une procedure

### Distillation

A utiliser si:

- tu veux compresser la qualite d un gros modele vers un plus petit
- tu veux baisser le cout d inference
- tu veux specialiser un petit modele

### DPO / ORPO / KTO

A utiliser si:

- tu as deja un bon SFT
- le sujet principal est la preference entre reponses

### Continued pretraining

A utiliser si:

- le modele manque surtout de connaissance de domaine
- tu as beaucoup de texte brut

### RL / GRPO / RFT

A utiliser si:

- tu peux calculer une note de qualite
- la tache est verifiable
- tu as deja une base SFT solide

## 8. Bonnes Pratiques

### Data

- mieux vaut 100 exemples excellents que 10 000 exemples mediocres
- garder un eval set a part
- dedupliquer
- garder la meme distribution que la vraie prod
- annoter les cas difficiles et les echecs recurrentes

### Training

- commencer petit
- faire des runs courts
- verifier le sur-apprentissage
- garder plusieurs checkpoints utiles
- comparer au modele de base avant de monter en complexite

### Evaluation

- eval avant
- eval apres
- eval sur holdout
- eval par slices metier
- eval humaine sur les cas critiques

## 9. Recommandations Tres Concretes Pour Toi

### Recommandation immediate

Utiliser:

- teacher `mistral` via Mascarade
- student `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- `samples-per-source=2`
- `max-source-samples=32` puis `64`
- `epochs=1` puis `2` si besoin

### Ce que je ne recommande pas tout de suite

- full fine-tuning
- DPO avant un bon SFT
- RL sans grader robuste
- gros students 7B+ sur cette carte

### Si tu veux monter d un cran

Deux directions serieuses:

1. meilleur teacher + meilleur eval
2. cloud tuning plus gros via Bedrock, Vertex ou autre service managed

## 10. Sources Primaires Utilisees

Etat de l art et docs verifiees le 2026-03-06:

- Hugging Face TRL SFTTrainer: https://huggingface.co/docs/trl/en/sft_trainer
- Hugging Face TRL DPOTrainer: https://huggingface.co/docs/trl/dpo_trainer
- Hugging Face TRL GRPOTrainer: https://huggingface.co/docs/trl/grpo_trainer
- Hugging Face TRL KTOTrainer: https://huggingface.co/docs/trl/en/kto_trainer
- Hugging Face TRL ORPOTrainer: https://huggingface.co/docs/trl/en/orpo_trainer
- Hugging Face TRL GKDTrainer: https://huggingface.co/docs/trl/main/en/gkd_trainer
- Hugging Face Transformers TRL integration: https://huggingface.co/docs/transformers/main/community_integrations/trl
- Hugging Face PEFT quick intro: https://huggingface.co/docs/transformers/peft
- Hugging Face PEFT quantization / QLoRA: https://huggingface.co/docs/peft/en/developer_guides/quantization
- Hugging Face PEFT LoRA variants: https://huggingface.co/docs/peft/main/en/developer_guides/lora
- PyTorch FSDP2 tutorial: https://docs.pytorch.org/tutorials/intermediate/FSDP_tutorial.html
- OpenAI supervised fine-tuning: https://developers.openai.com/api/docs/guides/supervised-fine-tuning
- OpenAI direct preference optimization: https://developers.openai.com/api/docs/guides/direct-preference-optimization
- OpenAI fine-tuning best practices: https://developers.openai.com/api/docs/guides/fine-tuning-best-practices
- OpenAI reinforcement fine-tuning: https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning
- Google Vertex AI tuning API: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/tuning
- Google Vertex AI tuning overview: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/tune-models
- Google Gemini supervised tuning: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-use-supervised-tuning
- Google Gemini preference tuning: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-use-preference-tuning
- Amazon Bedrock model customization overview: https://docs.aws.amazon.com/bedrock/latest/userguide/custom-models.html
- Amazon Bedrock fine-tuning / CPT: https://docs.aws.amazon.com/bedrock/latest/userguide/custom-model-fine-tuning.html
- Amazon Bedrock reinforcement fine-tuning: https://docs.aws.amazon.com/bedrock/latest/userguide/reinforcement-fine-tuning.html

## 11. Notes De Lecture

Si tu veux un chemin simple:

- aujourd hui, la meilleure option pour toi n est pas "gros fine-tuning local"
- c est "gros teacher + petit student bien distille + SFT local propre"

Autrement dit:

- le teacher apporte l intelligence specialisee
- le student apporte la vitesse, le cout et le local
