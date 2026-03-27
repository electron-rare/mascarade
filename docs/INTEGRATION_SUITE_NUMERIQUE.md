# Integration mascarade x La Suite Numerique

## La Suite Numerique

Initiative souveraine francaise (DINUM) + europeenne. MIT license. 500K+ utilisateurs.
GitHub: github.com/suitenumerique (35 repos)

### Composants officiels

| Composant | Fonction | Tech |
|-----------|----------|------|
| Docs | Wiki collaboratif | Django + React (16K stars) |
| Meet | Visioconference | LiveKit WebRTC |
| Drive/Fichiers | Stockage fichiers | Django + React |
| Tchap | Messagerie securisee | Matrix/Element (600K users) |
| Grist | Tableur/base de donnees | No-code |
| Conversations | Assistant IA | Pydantic AI + OpenAI-compatible |
| People | Gestion equipes | Django + React |
| Messages | Boite collaborative | Django + React |
| Projects | Gestion projets | React 19 |
| ProConnect | SSO federa | OIDC |

### Standards

- ProConnect : OIDC (authentification universelle)
- Matrix : messagerie temps reel (Tchap)
- Open Buro (openburo.eu) : standard EU orchestration workplace
- OpenAI-compatible : backend AI (Conversations)

## Integration mascarade

### P0 — Conversations comme backend (1h)

mascarade expose deja une API OpenAI-compatible. Config dans Conversations :

```env
AI_BASE_URL=http://192.168.0.119:8100/v1
AI_MODEL=codestral:codestral-latest
AI_API_KEY=aa441ffe110b493ecc08c7d8936fdf8f020986c72afc098f
```

Ca route toutes les requetes AI de La Suite vers les 29 agents mascarade.

### P1 — Tchap bot Matrix (1 jour)

Bot mascarade sur le protocole Matrix :
- matrix-nio (Python SDK)
- Repond aux mentions, DMs, slash commands
- Route vers les agents specialises

### P1 — ProConnect OIDC (1 jour)

mascarade comme client OIDC ProConnect :
- Authentification unifiee avec tous les outils Suite
- Contexte utilisateur par agent
- Audit trail

### P2 — RAG sur Docs/Wiki (2 jours)

Indexer le contenu Docs (wiki Suite Numerique) dans Qdrant :
- Webhook Docs → ingestion mascarade
- RAG queries depuis Conversations
- Search semantique cross-documents

### P2 — Meet transcription → RAG (2 jours)

WhisperX transcrit deja les reunions Meet :
- Post-process transcriptions via mascarade
- Resume automatique + action items
- Feed dans la base de connaissances

### P2 — Open Buro compliance (2 jours)

Aligner mascarade sur le standard Open Buro :
- Unified RAG/search API
- Cross-app event streaming
- Business object definitions

## Integration business (L'Electron Rare)

### n8n workflows avec mascarade

| Workflow | Trigger | Actions |
|----------|---------|---------|
| Email → CRM | Nouveau mail | Classification AI → Frappe update → draft reponse |
| Document → Filing | Upload Nextcloud | OCR Mistral → classification → Paperless |
| RDV → Brief | Cal.com event | RAG wiki → brief preparation |
| Lead → Scoring | Nouveau contact | AI scoring → Frappe assign → notification |

### er-ops copilot

Widget chat dans ops.saillant.cc :
- Agent agent-zero comme copilot
- Acces aux 29 agents specialises
- RAG sur toute la base de connaissances

## Timeline vers 1er mai

| Semaine | Tache |
|---------|-------|
| S14 (31 mars) | Config Conversations → mascarade backend |
| S15 (7 avril) | ProConnect OIDC + Tchap bot |
| S16 (14 avril) | RAG Docs + n8n workflows |
| S17 (21 avril) | Tests integration + polish |
| S18 (28 avril) | Deploy production + monitoring |
| **1er mai** | **LANCEMENT** |

## Refs

- lasuite.numerique.gouv.fr
- github.com/suitenumerique
- github.com/suitenumerique/conversations
- openburo.eu
- ProConnect OIDC docs
