# Mascarade — Manifest VM photon-machine

> **VM** : `photon-machine` — `192.168.0.119`
> **OS** : Photon OS (ESXi)
> **Date** : 2026-03-04
> **Signature** : *L'electron rare — unstable by design*

---

## 1. Zellij Sessions

Multiplexeur terminal : **Zellij 0.43.1**

### Sessions actives

| Session | Tabs | Panes | Role |
|---------|------|-------|------|
| **circular-jellyfish** | 6 | 8 | Session de travail principale |
| hopeful-sitar | 1 | 3 | Session courante (attach) |
| auspicious-weasel | 1 | 2 | Spare |
| inventive-lake | 1 | 2 | Spare |
| polite-donkey | 1 | 2 | Spare |
| zellig | 1 | 2 | Spare (mascarade) |

### circular-jellyfish — Tabs

| # | Nom | Agent | Contexte |
|---|-----|-------|----------|
| 1 | **webops VM SOLAR** | Claude Code | Ops-Console V3 SvelteKit, Fronius solar |
| 2 | **claude** | Claude Code | Mascarade repo |
| 3 | **codex** | OpenAI Codex | Mascarade repo |
| 4 | **skills & llm** | Claude Code | Skills, LLM config |
| 5 | **cockpit web** | — | Ops-Console dev |
| 6 | **update repo mascarade** | Claude Code | Migration, skills, setup |

### Config

- Chemin : `/root/.config/zellij/config.kdl`
- Sessions persistees : `/root/.cache/zellij/0.43.1/session_info/`
- Serialisation auto activee
- Layouts swap : vertical, horizontal, stacked, floating (enlarged/spread)

---

## 2. Agents CLI installes

| Agent | Modele | Config |
|-------|--------|--------|
| **Claude Code** | claude-opus-4-6 | `/root/.claude/settings.json` |
| **OpenAI Codex** | gpt-5.3-codex | `/root/.codex/config.toml` |
| **Mistral Vibe** | devstral-small | `/root/.vibe/config.toml` |

### MCP Servers (Codex)

| Serveur | Transport |
|---------|-----------|
| MCP_DOCKER | `docker mcp gateway run` |
| Notion | `https://mcp.notion.com/mcp` |
| Figma | `https://mcp.figma.com/mcp` |
| Linear | `https://mcp.linear.app/mcp` |
| GitHub | `https://api.githubcopilot.com/mcp/` |
| vibe-lite | `http://192.168.0.119:3922/mcp` |

---

## 3. Skills Registry

**124 skills** classes en 11 categories dans `/opt/skills-global/all/` :

| Categorie | Nb | Exemples |
|-----------|----|----------|
| electronics-hw | 32 | kicad, stm32, spice, pcb-design, fpga-design |
| devops-infra | 17 | docker-*, cloudflare-deploy, vercel-deploy, linux-admin |
| productivity | 17 | git-workflow, notion-*, sentry, yeet, playwright |
| web-frontend | 13 | react, vue, svelte, tailwind, figma-* |
| ai-ml | 8 | crewai, langchain, huggingface, rag-embeddings, mcp-dev |
| iot-embedded | 8 | esp-idf, homeassistant, mqtt-iot, platformio, rtos |
| design-creative | 7 | branding, ux-design, graphic-design, copywriting |
| business | 6 | seo-marketing, legal-rgpd, product-management |
| security | 6 | ethical-hacking, threat-model, reverse-engineering |
| web-backend | 5 | api-rest, database, nodejs-ts, python-dev |
| media | 5 | imagegen, sora, speech, transcribe, screenshot |

Symlinks plats a la racine pour compatibilite Claude Code / Codex.

### Skills projets

- `_projects/le-mystere-professeur-zacus/` : docs, firmware, printables, repo_hygiene, tooling
- `.system/` : skill-installer, skill-creator

---

## 4. Docker Stack (docker-studio-ai)

Services sur `192.168.0.119` :

| Container | Port | Role |
|-----------|------|------|
| zacus-ollama | 11434 | Serveur LLM local |
| zacus-studio-ai-gateway | 8787 | AI Gateway |
| zacus-open-webui | 3000 | Interface chat |
| zacus-redis | 6379 | Cache & broker |
| zacus-qdrant | 6333 | Base vectorielle |
| zacus-postgres | 5432 | Base relationnelle + pgvector |
| zacus-pihole | 53/8081 | DNS + ad blocking |
| zacus-homeassistant | 8123 | Domotique |
| zacus-ops-console | 80 | Cockpit web (Les CILS ZACUS) |
| zacus-discord-mcp-lite | 3921 | Discord MCP (optionnel) |
| zacus-vibe-mcp-lite | 3922 | Vibe MCP (optionnel) |

### llama.cpp

- Path : `/opt/llama.cpp`
- Repo : `https://github.com/ggerganov/llama.cpp`
- Commit : `ecd99d6a9`
- Build : cmake Release

---

## 5. Easter Eggs & References Culturelles

### 5.1 The Hitchhiker's Guide to the Galaxy (Douglas Adams)

| Ref | Lieu |
|-----|------|
| 42 specs et pipeline qui ne panique jamais | README ligne 59 : "42 secondes si tu es presse" |
| GPIO 42 (hardware easter egg) | `hardware/ui_freenove_allinone/README.md:32` — Audio I2S BCK |
| 42ms tick (`~24 FPS` cible) | `hardware/ui_freenove_allinone/README.md:287` |
| `dont_panic_generated.png` | Asset README |
| La serviette | Citee dans FAQ, doc_agent, hw_schematic_agent |
| Test PR #42 | Code OpenClaw |
| `badge_42_generated.gif` | GIF anime cache dans les assets |

### 5.2 Blade Runner / Philip K. Dick

- *"J'ai vu des evidence packs briller dans l'obscurite..."* — parodie du monologue Tears in Rain de Roy Batty
- *"Un evidence pack peut-il rever de conformite ?"* — parodie de Do Androids Dream of Electric Sheep?
- **QA Replicant** et les replicants dans les agents

### 5.3 Citations SF / dystopiques

Ann Leckie, Ted Chiang, Becky Chambers, N.K. Jemisin, Paolo Bacigalupi, Aldous Huxley, Liu Cixin, Adrian Tchaikovsky, Tolkien

### 5.4 Musique concrete & experimentale

Entetes caches dans 15+ fichiers avec citations de :

| Compositeur | Courant |
|-------------|---------|
| Pierre Schaeffer | Musique concrete |
| Eliane Radigue | Drone, electroacoustique |
| Luc Ferrari | Musique anecdotique |
| Bernard Parmegiani | GRM, electroacoustique |
| Francois Bayle | Acousmatique |
| Daphne Oram | Oramics, electronique UK |

### 5.5 Demoscene & Amiga Cracktro

FX Presets dans `scene_win_etape.json` :

| Preset | Mode |
|--------|------|
| `FX_PRESET_A` | demo |
| `FX_PRESET_B` | winner |
| `FX_PRESET_C` | boingball |
| `FX_MODE_A` | starfield3d |
| `FX_MODE_B` | dotsphere3d |
| `FX_MODE_C` | raycorridor |

Scroll texts : *"BRAVO BRIGADE Z"*, *"Vous avez la frequence - KEEP THE BEAT"*, *"BOINGBALL MODE"* — BPM 125

Refs : [pouet.net](https://www.pouet.net/), [awsm.de](https://www.awsm.de/jscracktros/), [markwrobel.dk](https://www.markwrobel.dk/), [theflatnet.de](https://www.theflatnet.de/)

### 5.6 Mini-jeu RtFM

Jeu de chasse aux phrases supprimees par le sanitizer, cache dans le README.

### 5.7 Liens caches

| Deguisement | Vrai lien |
|-------------|-----------|
| "Spec Generator FX" | Gangnam Style (YouTube) |
| Album Bandcamp | L'electron fou |
| Gate Runner | Lien fictif |

### 5.8 Noms mysterieux

- **le-mystere-professeur-zacus** — le projet racine
- **RTC_BL_PHONE** — repo cross-repo ESP-NOW (`electron-rare/RTC_BL_PHONE`)
- **KIKIFOU** — reference interne

### 5.9 Easter eggs saisonniers

Le script OpenClaw affiche des messages differents selon la date :

Paques, Halloween, Noel, Diwali, etc.

### 5.10 Taglines CLI OpenClaw

50+ taglines humoristiques en rotation dans le CLI.

### 5.11 FX modes des agents

Bulk Edit Party FX, QA Replicant, Gate Runner...

### 5.12 Historique des noms du bot

```
MoldBot → MoltBot → ClawdBot → OpenClaw
```

### 5.13 Commits

Claude Opus 4.6 co-auteur officiel :

```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### 5.14 Funk & Groove

- *"Bienvenue dans le cockpit le plus funky du multivers!"*
- *"Si tu rates un bouton, c'est que tu danses trop fort."*
- *"Si tu vois un plasma violet, c'est que tu es dans le groove."*
- *"Si un enfant demande 'c'est quoi un ion ?', reponds 'c'est un electron qui a trop fait la fete !'"*
- Validation officielle : *"Ce projet a ete valide par un oscilloscope, un grille-pain, et une IA qui adore les enigmes."*

---

## 6. Arborescence du repo

```
mascarade/
├── api/                    # API Hono (TypeScript)
├── core/                   # Orchestrateur LLM (Python)
├── skills/                 # Docs skills Mascarade
├── deploy/                 # Dockerfiles
├── docs/                   # Documentation ops
├── scripts/                # Scripts helpers
├── opt/                    # Migration /opt VM
│   ├── docker-studio-ai/   # Stack Docker complete (3.8MB)
│   ├── llama.cpp/           # Ref + install script
│   └── skills-global/       # 124 skills categories + symlinks
├── .claude/
│   └── skills/              # Skills projet (categories + _projects)
├── setup                    # Installateur TUI
├── docker-compose.yml       # Genere par setup
├── CLAUDE.md                # Conventions projet
└── MANIFEST.md              # Ce fichier
```

---

*mascarade v0.1.0 — photon-machine — 2026-03-04*
