# Modeles Recents Compatibles Avec Ce Pipeline

Date de reference: 2026-03-07

But:

- comparer les modeles ouverts recents qui ont du sens pour `mascarade`
- noter l effort de portage reel avec le trainer local actuel
- separer les modeles "student local" des modeles "teacher / inference"

Contrainte locale importante:

- le trainer actuel est centre sur un chemin texte + QLoRA:
  - `AutoModelForCausalLM`
  - cibles LoRA statiques par famille
  - formatage chat code en dur
- references:
  - `finetune/train_local.py`
  - `finetune/requirements.txt`

## Tableau rapide

| Modele | Source officielle | Etat 2026 | Fit 4090 local | Effort de portage | Verdict |
|---|---|---|---|---|---|
| `Qwen/Qwen3-8B` | Qwen HF | baseline actuelle | bon | faible | meilleur student dense deja valide |
| `Qwen/Qwen3.5-9B` | Qwen HF + docs Qwen | tres recent | moyen | moyen | bon candidat solo, mauvais candidat dual |
| `Qwen/Qwen3.5-9B-Base` | Qwen HF + docs Qwen | tres recent | bon | moyen | meilleur candidat Qwen3.5 pour fine-tuning local |
| `mistralai/Devstral-Small-2507` | Mistral HF | actuel | moyen | moyen/fort | bon teacher ou inference, pas premier student ici |
| `Mistral Small 3.1` | docs Mistral | actuel | moyen | fort | plausible en solo apres portage, pas drop-in |
| `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` | Qwen HF + docs Qwen | tres recent | non | fort | teacher-only dans ce pipeline |
| `Qwen3-Coder-480B-A35B-Instruct` | blog Qwen | frontier coding | non | hors scope local | teacher distant, pas student local |

## Detail par modele

### 1. `Qwen/Qwen3-8B`

Pourquoi il reste fort ici:

- deja integre proprement dans le trainer
- deja valide en triple charges locales
- chemin LoRA / chat template / tokenizer deja maitrise

Verdict:

- c est encore le meilleur point d equilibre pour un student local sur cette machine

### 2. `Qwen/Qwen3.5-9B`

Ce que disent les sources:

- la carte officielle indique une architecture `Qwen3_5ForConditionalGeneration`
- le `config.json` officiel du modele annonce `model_type=qwen3_5`
- le `config.json` officiel annonce aussi `transformers_version=4.57.0.dev0`
- la doc Qwen positionne `Qwen3.5` comme la ligne recente de la famille

Impact concret sur ce repo:

- ce n est pas un vrai drop-in pour notre pin stable `transformers==4.57.6`
- avant portage, `venv_tuning` n exposait pas `transformers.models.qwen3_5`
- il a fallu:
  - ajouter un chemin de chargement `Qwen3_5ForConditionalGeneration`
  - monter `venv_tuning` sur `transformers` `main`

Mesures locales faites ici:

- smoke solo OK:
  - commande: `python finetune/run_local.py stm32 --device gpu --model Qwen/Qwen3.5-9B --offline --max-samples 2 --epochs 1 --seq-len 256`
  - loss: `1.2028`
  - adapter: `.tmp/qwen35_smoke_single/adapter`
- dual run NON:
  - commande: `Q8B_MODEL=Qwen/Qwen3.5-9B MODE=dual-8b-512 ./scripts/triple_train_4090.sh`
  - les deux runs cassent pendant le chargement des poids
  - pic VRAM echantillonne: `23661 MiB / 24564 MiB`
  - chaque process monte autour de `10.6 a 11.2 Go` avant OOM

Verdict:

- bon candidat si on veut un test "nouvelle generation" en solo
- mauvais candidat pour `2 x` sur une seule RTX 4090
- le blocage est la VRAM de chargement, pas la sequence

### 2b. `Qwen/Qwen3.5-9B-Base`

Ce que disent les sources:

- la carte officielle le positionne comme version base, orientee fine-tuning
- Qwen precise que les tokens de chat ont ete entraines pour simplifier le LoRA sans retoucher les embeddings

Pourquoi il est plus pertinent ici:

- meme famille recente que `Qwen3.5-9B`
- meilleur point de depart pour un vrai student specialise
- plus coherent avec le but du pipeline local que la version post-trained

Verdict:

- meilleur candidat Qwen3.5 pour fine-tuning local sur cette machine
- a preferer a `Qwen/Qwen3.5-9B` si le but est un student de domaine

### 3. `mistralai/Devstral-Small-2507`

Pourquoi il est interessant:

- recent
- cible coding / agentic
- tres bon candidat teacher local ou inference

Pourquoi je ne le prends pas comme premier student ici:

- notre trainer n a pas encore de voie propre `mistral`
- le formatage chat et les cibles LoRA actuelles sont surtout prevus pour `qwen` / `llama`

Verdict:

- excellent candidat teacher
- student local possible, mais seulement apres un portage Mistral explicite

### 4. `Mistral Small 3.1`

Ce que disent les sources:

- Mistral le positionne comme un modele local capable de tourner sur une single RTX 4090

Pourquoi le portage est plus couteux ici:

- famille differente
- modele recent et plus complexe que notre chemin `AutoModelForCausalLM` de base
- risque de devoir revoir tokenizer, template et eventuellement classe de chargement

Verdict:

- plausible pour un essai solo
- pas le premier test que je ferais avant d avoir stabilise Qwen3.5

### 5. `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`

Ce que disent les sources:

- checkpoint GPTQ Int4
- modele recent hybride / MoE oriente serving

Pourquoi il est `teacher-only` ici:

- checkpoint GPTQ deja quantifie, pas bon point d entree pour notre chemin QLoRA
- modele plus complexe que notre chemin student texte standard
- utile comme teacher ou inference, pas comme student local

Verdict:

- `teacher-only` dans ce pipeline
- le code refuse explicitement ce modele comme student

### 6. `Qwen3-Coder-480B-A35B-Instruct`

Ce que disent les sources:

- Qwen le presente comme son gros modele coder agentique de pointe

Verdict:

- pas un student local pour cette machine
- utile comme teacher distant ou reference de qualite

## Recommandation pratique

Ordre de priorite pour cette machine et ce repo:

1. garder `Qwen/Qwen3-8B` comme student dense stable
2. utiliser `Qwen/Qwen3.5-9B-Base` si on veut un student Qwen3.5
3. garder `Qwen/Qwen3.5-9B` pour du solo / comparatif
4. utiliser `Devstral-Small-2507` comme teacher / inference
5. ne pas viser `2 x Qwen3.5-9B` sur cette 4090

## Changements techniques deja faits pour Qwen3.5

- `finetune/train_local.py`:
  - detection `model_type=qwen3_5`
  - chargement via `Qwen3_5ForConditionalGeneration`
- `finetune/run_local.py` et `finetune/train_local.py`:
  - refus explicite de certains modeles `teacher-only`
- `venv_tuning`:
  - `transformers` passe sur une build `main` qui expose `qwen3_5`
- `scripts/bootstrap_finetune_env.sh`:
  - support `TRANSFORMERS_CHANNEL=main` pour rendre `Qwen3.5` reproductible

## Sources officielles

- Qwen3.5 docs: https://docs.qwen.ai/
- Qwen3.5 model card: https://huggingface.co/Qwen/Qwen3.5-9B
- Qwen3.5 Base model card: https://huggingface.co/Qwen/Qwen3.5-9B-Base
- Qwen3.5 35B A3B GPTQ Int4: https://huggingface.co/Qwen/Qwen3.5-35B-A3B-GPTQ-Int4
- Qwen3-Coder: https://qwenlm.github.io/blog/qwen3-coder/
- Devstral Small 2507: https://huggingface.co/mistralai/Devstral-Small-2507
- Mistral models overview: https://docs.mistral.ai/getting-started/models/models_overview/
