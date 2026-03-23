# Intégration Mistral Studio avec Mascarade

Ce guide explique comment intégrer Mistral Studio avec le framework Mascarade pour le finetuning et l'utilisation de modèles spécialisés.

## Décision d'architecture verrouillée

Séparation opératoire retenue à partir du `2026-03-22`:

- `Kill_LIFE` cockpit opérateur reste en appels directs vers l'API Mistral pour:
  - health Studio
  - handoff opérateur
  - administration agents / fichiers / fine-tune
- le runtime `Mascarade` dans le repo actif `/Users/electron/Documents/Projets/mascarade`
  utilise le provider routeur `mistral-agents` pour les appels applicatifs aux agents distants
- le repo historique `mascarade-main` reste une référence de lecture uniquement, jamais une cible d'implémentation

Conséquence:
- la configuration Mistral de runtime est documentée ici, une seule fois
- aucun secret ni ID réel ne doit être recopié dans le repo actif

## Configuration

### 1. Configuration de l'API Mistral Studio

Modifiez votre fichier `.env` pour ajouter votre clé API Mistral :

```env
MISTRAL_API_KEY="votre_cle_api_mistral_studio"
```

### 2. Configuration de LiteLLM

Le fichier `tools/litellm-config.yaml` a été mis à jour avec les modèles Mistral :

```yaml
model_list:
  - model_name: mistral-small-latest
    litellm_params:
      model: mistral/mistral-small-latest
      api_key: ${MISTRAL_API_KEY}
  - model_name: mistral-medium-latest
    litellm_params:
      model: mistral/mistral-medium-latest
      api_key: ${MISTRAL_API_KEY}
  - model_name: mistral-large-latest
    litellm_params:
      model: mistral/mistral-large-latest
      api_key: ${MISTRAL_API_KEY}
```

### 3. Configuration Mascarade

Dans `core/mascarade/config.py`, les paramètres suivants ont été ajoutés :

```python
# Mistral Studio
mistral_api_base: str = "https://api.mistral.ai/v1"
mistral_default_model: str = "mistral-large-latest"
mistral_agents_api_mode: str = "beta"
mistral_agent_sentinelle_id: str = ""
mistral_agent_tower_id: str = ""
mistral_agent_forge_id: str = ""
mistral_agent_devstral_id: str = ""
```

### 4. Configuration des agents distants Mistral

Le repo actif supporte maintenant un provider routeur dédié `mistral-agents` et un bridge
`agents.mistral_agents` pour les agents distants AI Studio.

Variables à définir dans l’environnement actif du core:

```env
MISTRAL_AGENTS_API_MODE=beta
MISTRAL_AGENT_SENTINELLE_ID=ag_xxx
MISTRAL_AGENT_TOWER_ID=ag_xxx
MISTRAL_AGENT_FORGE_ID=ag_xxx
MISTRAL_AGENT_DEVSTRAL_ID=ag_xxx
```

Contraintes:
- ne pas commiter les IDs réels ni les clés API dans le repo
- `mistral-agents` n’est enregistré par le routeur que si `MISTRAL_API_KEY` est présent
  et qu’au moins un `MISTRAL_AGENT_*_ID` est configuré
- le mode recommandé est `beta`; le code garde un fallback vers l’endpoint deprecated
  `/v1/agents/{id}/completions` pour la reprise
- le cockpit `Kill_LIFE` peut utiliser les mêmes IDs, mais il continue d'appeler Mistral en direct;
  le runtime `Mascarade` passe par `mistral-agents`

## Utilisation des modèles Mistral

### Modèles disponibles

- `mistral-small-latest` - Modèle rapide et économique
- `mistral-medium-latest` - Équilibre performance/prix
- `mistral-large-latest` - Meilleure qualité
- `codestral-latest` - Spécialisé pour le code

### Utilisation via le router

```python
from mascarade.router import Router

router = Router()
response = await router.send(
    messages=[{"role": "user", "content": "Hello from Mistral!"}],
    provider="mistral",
    model="mistral-large-latest"
)
```

### Utilisation des agents Mistral distants via le router

```python
from mascarade.router import Router

router = Router()
response = await router.send(
    messages=[{"role": "user", "content": "Diagnostique ce cluster"}],
    provider="mistral-agents",
    model="agent:sentinelle",
)
```

Le provider routeur dédié est implémenté dans:
- `/Users/electron/Documents/Projets/mascarade/core/mascarade/router/providers/mistral_agents.py`

Le bridge d’agents distants est implémenté dans:
- `/Users/electron/Documents/Projets/mascarade/core/mascarade/agents/mistral_agents.py`

## Codestral FIM dans le repo actif

La fermeture de `T-MS-023` est faite dans le repo actif sans créer un second provider.

Décision retenue:
- ne pas créer `codestral_fim.py`
- conserver `core/mascarade/router/providers/codestral.py` comme surface unique pour le chat code + le FIM
- exposer le FIM via les routes:
  - core: `/v1/api/providers/codestral/fim`
  - gateway TypeScript: `/api/providers/codestral/fim`

Exemple d'appel core:

```bash
curl -X POST http://localhost:8100/v1/api/providers/codestral/fim \
  -H "Authorization: Bearer $MASCARADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "def add(a, b):\n",
    "suffix": "\nresult = add(1, 2)\n",
    "max_tokens": 64
  }'
```

Ce chemin remplace explicitement l'idée d'un provider `codestral_fim` séparé.

## Fine-tuning avec Mistral Studio

### Préparation du dataset

Un exemple de dataset FreeCAD a été créé dans `finetune/datasets/freecad_chat.jsonl` avec le format requis par Mistral Studio.

### Script de construction

Le script canonique `finetune/datasets/build_freecad_dataset.py` permet de générer des datasets supplémentaires.

### Processus de fine-tuning

1. **Préparer le dataset** au format JSONL avec des conversations
2. **Soumettre à Mistral Studio** via l'API ou l'interface web
3. **Surveiller la progression** du job de fine-tuning
4. **Tester le modèle** une fois le fine-tuning terminé
5. **Intégrer avec Mascarade** en mettant à jour la configuration

### Exemple de notebook

Un notebook complet est disponible dans `finetune/notebooks/finetune_freecad_mistral_studio.ipynb` démontrant tout le processus.

## Agent FreeCAD

Un agent spécialisé FreeCAD a été créé et intégré :

### Caractéristiques

- **Nom** : `freecad-designer`
- **Modèle par défaut** : `mistral-large-latest`
- **Température** : 0.3 (pour des réponses précises)
- **Max tokens** : 2048

### Fonctionnalités

```python
from mascarade.agents import FreeCADAgent

agent = FreeCADAgent()

# Générer un script FreeCAD
script = await agent.generate_freecad_script("créer un engrenage paramétrique", router)

# Expliquer un concept
explanation = await agent.explain_freecad_concept("contraintes d'esquisse", router)

# Déboguer un problème
solution = await agent.debug_freecad_issue("problème de recomputation", router)
```

### Intégration automatique

L'agent FreeCAD est automatiquement enregistré dans le registre des agents via `register_default_skills()`.

## Bonnes pratiques

### Gestion des clés API

- Utilisez toujours des variables d'environnement pour les clés API
- Ne commitez jamais les clés dans le code ou les fichiers de configuration
- Utilisez `.env` et ajoutez-le à `.gitignore`

### Optimisation des coûts

- Utilisez `mistral-small-latest` pour les tâches simples
- Réservez `mistral-large-latest` pour les tâches complexes
- Configurez des limites de tokens appropriées

### Monitoring

- Surveillez l'utilisation via le tableau de bord Mistral Studio
- Configurez des alertes pour les dépenses
- Revue régulière des logs d'utilisation

## Dépannage

### Problèmes courants

1. **Erreur d'authentification** : Vérifiez que `MISTRAL_API_KEY` est correctement configuré
2. **Modèle non trouvé** : Assurez-vous que le nom du modèle est correct
3. **Limites de quota** : Vérifiez votre quota sur le tableau de bord Mistral
4. **Problèmes de réseau** : Vérifiez la connectivité à `api.mistral.ai`

### Logs et debugging

Activez les logs détaillés dans la configuration :

```python
import logging
logging.getLogger("mascarade.router.providers.mistral").setLevel(logging.DEBUG)
```

## Ressources supplémentaires

- [Documentation Mistral Studio](https://docs.mistral.ai/)
- [API Reference](https://docs.mistral.ai/api/)
- [Guide de fine-tuning](https://docs.mistral.ai/fine-tuning/)

## Support

Pour toute question ou problème avec l'intégration Mistral Studio, contactez l'équipe Mascarade ou consultez la documentation officielle Mistral AI.
