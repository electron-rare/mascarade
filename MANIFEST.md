# Mascarade — Manifest VM photon-machine

> **VM** : `photon-machine` — `192 (repo compagnon hors worktree).168 (repo compagnon hors worktree).0 (repo compagnon hors worktree).119`
> **OS** : Photon OS (ESXi)
> **Date** : 2026-03-04
> **Signature** : *L'electron rare — unstable by design*

> Note:
> ce fichier est un snapshot machine/operator, pas une source de verite pour
> l'ownership des repos ni pour le chemin de release (repo compagnon hors worktree).
> Le contrat multi-repo actif est fige dans
> `crazy_life/docs/REPO_CARTOGRAPHY_2026-03-07 (repo compagnon hors worktree).md` (repo compagnon hors worktree) (repo compagnon hors worktree).

---

## 1 (repo compagnon hors worktree). Zellij Sessions

Multiplexeur terminal : **Zellij 0 (repo compagnon hors worktree).43 (repo compagnon hors worktree).1**

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

- Chemin : `/root/ (repo compagnon hors worktree).config/zellij/config (repo compagnon hors worktree).kdl`
- Sessions persistees : `/root/ (repo compagnon hors worktree).cache/zellij/0 (repo compagnon hors worktree).43 (repo compagnon hors worktree).1/session_info/`
- Serialisation auto activee
- Layouts swap : vertical, horizontal, stacked, floating (enlarged/spread)

---

## 2 (repo compagnon hors worktree). Agents CLI installes

| Agent | Modele | Config |
|-------|--------|--------|
| **Claude Code** | claude-opus-4-6 | `/root/ (repo compagnon hors worktree).claude/settings (repo compagnon hors worktree).json` |
| **OpenAI Codex** | gpt-5 (repo compagnon hors worktree).3-codex | `/root/ (repo compagnon hors worktree).codex/config (repo compagnon hors worktree).toml` |
| **Mistral Vibe** | devstral-small | `/root/ (repo compagnon hors worktree).vibe/config (repo compagnon hors worktree).toml` |

### MCP Servers (Codex)

| Serveur | Transport |
|---------|-----------|
| MCP_DOCKER | `docker mcp gateway run` |
| Notion | `https://mcp (repo compagnon hors worktree).notion (repo compagnon hors worktree).com/mcp` |
| Figma | `https://mcp (repo compagnon hors worktree).figma (repo compagnon hors worktree).com/mcp` |
| Linear | `https://mcp (repo compagnon hors worktree).linear (repo compagnon hors worktree).app/mcp` |
| GitHub | `https://api (repo compagnon hors worktree).githubcopilot (repo compagnon hors worktree).com/mcp/` |
| vibe-lite | `http://192 (repo compagnon hors worktree).168 (repo compagnon hors worktree).0 (repo compagnon hors worktree).119:3922/mcp` |

---

## 3 (repo compagnon hors worktree). Skills Registry

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

Symlinks plats a la racine pour compatibilite Claude Code / Codex (repo compagnon hors worktree).

### Skills projets

- `_projects/le-mystere-professeur-zacus/` : docs, firmware, printables, repo_hygiene, tooling
- ` (repo compagnon hors worktree).system/` : skill-installer, skill-creator

---

## 4 (repo compagnon hors worktree). Docker Stack (docker-studio-ai)

Services sur `192 (repo compagnon hors worktree).168 (repo compagnon hors worktree).0 (repo compagnon hors worktree).119` :

| Container | Port | Role |
|-----------|------|------|
| zacus-ollama | 11434 | Serveur LLM local |
| zacus-studio-ai-gateway | 8787 | AI Gateway |
| zacus-redis | 6379 | Cache & broker |
| zacus-qdrant | 6333 | Base vectorielle |
| zacus-postgres | 5432 | Base relationnelle + pgvector |
| zacus-pihole | 53/8081 | DNS + ad blocking |
| zacus-homeassistant | 8123 | Domotique |
| zacus-ops-console | 80 | Cockpit web (Les CILS ZACUS) |
| zacus-discord-mcp-lite | 3921 | Discord MCP (optionnel) |
| zacus-vibe-mcp-lite | 3922 | Vibe MCP (optionnel) |

### llama (repo compagnon hors worktree).cpp

- Path : `/opt/llama (repo compagnon hors worktree).cpp`
- Repo : `https://github (repo compagnon hors worktree).com/ggerganov/llama (repo compagnon hors worktree).cpp`
- Commit : `ecd99d6a9`
- Build : cmake Release

---

## 5 (repo compagnon hors worktree). Easter Eggs & References Culturelles

### 5 (repo compagnon hors worktree).1 The Hitchhiker's Guide to the Galaxy (Douglas Adams)

| Ref | Lieu |
|-----|------|
| 42 specs et pipeline qui ne panique jamais | README ligne 59 : "42 secondes si tu es presse" |
| GPIO 42 (hardware easter egg) | `hardware/ui_freenove_allinone/README (repo compagnon hors worktree).md:32` — Audio I2S BCK |
| 42ms tick (`~24 FPS` cible) | `hardware/ui_freenove_allinone/README (repo compagnon hors worktree).md:287` |
| `dont_panic_generated (repo compagnon hors worktree).png` | Asset README |
| La serviette | Citee dans FAQ, doc_agent, hw_schematic_agent |
| Test PR #42 | Code OpenClaw |
| `badge_42_generated (repo compagnon hors worktree).gif` | GIF anime cache dans les assets |

### 5 (repo compagnon hors worktree).2 Blade Runner / Philip K (repo compagnon hors worktree). Dick

- *"J'ai vu des evidence packs briller dans l'obscurite (repo compagnon hors worktree). (repo compagnon hors worktree). (repo compagnon hors worktree)."* — parodie du monologue Tears in Rain de Roy Batty
- *"Un evidence pack peut-il rever de conformite ?"* — parodie de Do Androids Dream of Electric Sheep?
- **QA Replicant** et les replicants dans les agents

### 5 (repo compagnon hors worktree).3 Citations SF / dystopiques

Ann Leckie, Ted Chiang, Becky Chambers, N (repo compagnon hors worktree).K (repo compagnon hors worktree). Jemisin, Paolo Bacigalupi, Aldous Huxley, Liu Cixin, Adrian Tchaikovsky, Tolkien

### 5 (repo compagnon hors worktree).4 Musique concrete & experimentale

Entetes caches dans 15+ fichiers avec citations de :

| Compositeur | Courant |
|-------------|---------|
| Pierre Schaeffer | Musique concrete |
| Eliane Radigue | Drone, electroacoustique |
| Luc Ferrari | Musique anecdotique |
| Bernard Parmegiani | GRM, electroacoustique |
| Francois Bayle | Acousmatique |
| Daphne Oram | Oramics, electronique UK |

Constellation etendue liee aux nouvelles thematiques du manifeste :

| Compositeur / groupe | Source | Axe utile |
|----------------------|--------|-----------|
| Delia Derbyshire | [University of Manchester - Delia Derbyshire project](https://www (repo compagnon hors worktree).library (repo compagnon hors worktree).manchester (repo compagnon hors worktree).ac (repo compagnon hors worktree).uk/services/digitisation-services/projects/delia-derbyshire/index (repo compagnon hors worktree).htm), [Delia Derbyshire Day - archive](https://deliaderbyshireday (repo compagnon hors worktree).com/dd-archive/) | radiophonie, science-fiction sonore, bricolage magnetique, imagination DIY |
| Pauline Oliveros | [Pauline Oliveros Trust - about](https://www (repo compagnon hors worktree).paulineoliveros (repo compagnon hors worktree).us/about (repo compagnon hors worktree).html), [Center for Deep Listening - Pauline Oliveros](https://www (repo compagnon hors worktree).deeplistening (repo compagnon hors worktree).rpi (repo compagnon hors worktree).edu/deep-listening/pauline-oliveros/) | Deep Listening, attention elargie, rituel, ecoute collective, conscience sonore |
| Suzanne Ciani | [Suzanne Ciani - bio](https://www (repo compagnon hors worktree).sevwave (repo compagnon hors worktree).com/bio), [YBCA - Suzanne Ciani](https://ybca (repo compagnon hors worktree).org/artist/suzanne-ciani/) | Buchla, logos sonores, fluidite aquatique, synthese sensuelle, machine hospitaliere mais fantasque |
| Laurie Anderson | [Britannica - Laurie Anderson](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Laurie-Anderson) | voix, medias, ironie froide, performance techno-litteraire |
| Sun Ra | [NEA Jazz Masters - Sun Ra](https://www (repo compagnon hors worktree).arts (repo compagnon hors worktree).gov/honors/jazz/sun-ra) | afrofuturisme, cosmologie, freak orchestra, mythe spatial |
| Tangerine Dream | [Official website](https://www (repo compagnon hors worktree).tangerinedreammusic (repo compagnon hors worktree).com/) | sequencers, kosmische musik, voyage nocturne, fantasy synth, route cosmique |
| Ryoji Ikeda | [Official biography](https://www (repo compagnon hors worktree).ryojiikeda (repo compagnon hors worktree).com/biography/), [Arts at CERN - Ryoji Ikeda](https://arts (repo compagnon hors worktree).cern/artist/ryoji-ikeda/) | data, glitch, precision mathematique, lumiere froide, abstraction systemique |
| Annea Lockwood | [Official biography](https://www (repo compagnon hors worktree).annealockwood (repo compagnon hors worktree).com/biography/), [Fromm Foundation - Annea Lockwood](https://frommfoundation (repo compagnon hors worktree).fas (repo compagnon hors worktree).harvard (repo compagnon hors worktree).edu/people/annea-lockwood) | ecologie sonore, pianos rituels, paysages naturels, matiere acoustique brute |
| Terry Riley | [Cantaloupe Music - Terry Riley](https://cantaloupemusic (repo compagnon hors worktree).com/artists/terry-riley), [Bang on a Can - Terry Riley 90th Birthday Celebration](https://bangonacan (repo compagnon hors worktree).org/events/terry-riley-90th-birthday-celebration/) | repetition psychedelique, minimalisme extatique, boucle cosmique, transe joyeuse |

Raccourcis de reinjection :
- `Oliveros + Lockwood` pour l'ecoute, le rituel, l'environnement et la lenteur active (repo compagnon hors worktree).
- `Derbyshire + Ciani + Ikeda` pour machine, studio, signal, data et imaginaire techno (repo compagnon hors worktree).
- `Sun Ra + Tangerine Dream + Riley` pour cosmique, fantasy, route nocturne et trance (repo compagnon hors worktree).
- `Laurie Anderson` pour voix-off, medias, interface et sarcasme elegant (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).5 Demoscene & Amiga Cracktro

FX Presets dans `scene_win_etape (repo compagnon hors worktree).json` :

| Preset | Mode |
|--------|------|
| `FX_PRESET_A` | demo |
| `FX_PRESET_B` | winner |
| `FX_PRESET_C` | boingball |
| `FX_MODE_A` | starfield3d |
| `FX_MODE_B` | dotsphere3d |
| `FX_MODE_C` | raycorridor |

Scroll texts : *"BRAVO BRIGADE Z"*, *"Vous avez la frequence - KEEP THE BEAT"*, *"BOINGBALL MODE"* — BPM 125

Refs : [pouet (repo compagnon hors worktree).net](https://www (repo compagnon hors worktree).pouet (repo compagnon hors worktree).net/), [awsm (repo compagnon hors worktree).de](https://www (repo compagnon hors worktree).awsm (repo compagnon hors worktree).de/jscracktros/), [markwrobel (repo compagnon hors worktree).dk](https://www (repo compagnon hors worktree).markwrobel (repo compagnon hors worktree).dk/), [theflatnet (repo compagnon hors worktree).de](https://www (repo compagnon hors worktree).theflatnet (repo compagnon hors worktree).de/)

### 5 (repo compagnon hors worktree).6 Mini-jeu RtFM

Jeu de chasse aux phrases supprimees par le sanitizer, cache dans le README (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).7 Liens caches

| Deguisement | Vrai lien |
|-------------|-----------|
| "Spec Generator FX" | Gangnam Style (YouTube) |
| Album Bandcamp | L'electron fou |
| Gate Runner | Lien fictif |

### 5 (repo compagnon hors worktree).8 Noms mysterieux

- **le-mystere-professeur-zacus** — le projet racine
- **RTC_BL_PHONE** — repo cross-repo ESP-NOW (`electron-rare/RTC_BL_PHONE`)
- **KIKIFOU** — reference interne

### 5 (repo compagnon hors worktree).9 Easter eggs saisonniers

Le script OpenClaw affiche des messages differents selon la date :

Paques, Halloween, Noel, Diwali, etc (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).10 Taglines CLI OpenClaw

50+ taglines humoristiques en rotation dans le CLI (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).11 FX modes des agents

Bulk Edit Party FX, QA Replicant, Gate Runner (repo compagnon hors worktree). (repo compagnon hors worktree). (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).12 Historique des noms du bot

```
MoldBot → MoltBot → ClawdBot → OpenClaw
```

### 5 (repo compagnon hors worktree).13 Commits

Claude Opus 4 (repo compagnon hors worktree).6 co-auteur officiel :

```
Co-Authored-By: Claude Opus 4 (repo compagnon hors worktree).6 <noreply@anthropic (repo compagnon hors worktree).com>
```

### 5 (repo compagnon hors worktree).14 Funk & Groove

- *"Bienvenue dans le cockpit le plus funky du multivers!"*
- *"Si tu rates un bouton, c'est que tu danses trop fort (repo compagnon hors worktree)."*
- *"Si tu vois un plasma violet, c'est que tu es dans le groove (repo compagnon hors worktree)."*
- *"Si un enfant demande 'c'est quoi un ion ?', reponds 'c'est un electron qui a trop fait la fete !'"*
- Validation officielle : *"Ce projet a ete valide par un oscilloscope, un grille-pain, et une IA qui adore les enigmes (repo compagnon hors worktree)."*

### 5 (repo compagnon hors worktree).15 Psychedelique, fantasy & freaks

Le manifeste assume maintenant une ligne esthetique plus explicite, avec un socle de references web documentees :

| Axe | Sources | Injection Mascarade |
|-----|---------|--------------------|
| Psychedelique | [Tate - Yayoi Kusama](https://shop (repo compagnon hors worktree).tate (repo compagnon hors worktree).org (repo compagnon hors worktree).uk/yayoi-kusama-infinity-mirror-room-purple-postcard/26132 (repo compagnon hors worktree).html), [Tate - Gustav Metzger](https://shop (repo compagnon hors worktree).tate (repo compagnon hors worktree).org (repo compagnon hors worktree).uk/gustav-metzger-liquid-crystal-environment/radlan2206 (repo compagnon hors worktree).html) | repetition, miroirs, lumiere, motifs obsessifs, couleurs mouvantes, plasma violet |
| Fantasy | [Britannica - fantasy](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/art/fantasy-narrative-genre), [The Met Cloisters - A Magical Menagerie](https://www (repo compagnon hors worktree).metmuseum (repo compagnon hors worktree).org/exhibitions/a-magical-menagerie) | autres mondes, etres surnaturels, bestiaire, portail opalin, grimoires de specs |
| Freaks | [Criterion - Freaks (1932)](https://www (repo compagnon hors worktree).criterion (repo compagnon hors worktree).com/films/29015-freaks) | carnaval mutant, troupe d'outsiders, freakshow de precision, compassion pour les marges |

Cette couche n'efface pas la rigueur technique (repo compagnon hors worktree). Elle sert de vernis narratif pour les CLIs, les FX, les easter eggs et la mythologie Mascarade (repo compagnon hors worktree).

- Ton cible : tech baroque, freakshow de precision, fantasy neon (repo compagnon hors worktree).
- Vocabulaire autorise : multivers, portail, glyphes, plasma, gobelins du build, bal des replicants (repo compagnon hors worktree).
- Contrainte implicite : garder le contraste entre chaos esthetique et execution propre (repo compagnon hors worktree).
- Raccourci de direction : Kusama pour l'immersion visuelle, Metzger pour la matiere mouvante, fantasy pour l'etrangete, Browning pour la troupe d'outsiders (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).16 Canon psychedelique

| Figure | Source | Ce qui nourrit Mascarade |
|--------|--------|--------------------------|
| Timothy Leary | [Britannica - Timothy Leary](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Timothy-Leary) | expansion de conscience, contre-culture, rhetorique du basculement |
| Albert Hofmann | [Britannica - Albert Hofmann](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Albert-Hofmann) | laboratoire, perception alteree, discipline chimique, imaginaire du reveal |
| Aldous Huxley | [Britannica - Aldous Huxley](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Aldous-Huxley) | satire dystopique, vision, lucidite ironique, `The Doors of Perception` |
| Alexander Shulgin | [Shulgin Foundation - Archive](https://shulginfoundation (repo compagnon hors worktree).org/shulgin-archive/), [Purdue Archives](https://archives (repo compagnon hors worktree).lib (repo compagnon hors worktree).purdue (repo compagnon hors worktree).edu/agents/people/2485) | folklore du labo, precision documentaire, psychonautique ecrite comme catalogue et carnet |

Regle editoriale : on pioche ici une energie sensorielle et un imaginaire de l'experience, pas un manifeste d'usage (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).17 Beat Generation & gonzo

| Courant | Source | Injection Mascarade |
|---------|--------|---------------------|
| Beat Generation | [Britannica - Beat movement](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/art/Beat-movement) | route, improvisation, prose qui pulse, fraternite d'outsiders |
| Gonzo journalism | [Britannica - gonzo journalism](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/topic/gonzo-journalism), [Britannica - Hunter S (repo compagnon hors worktree). Thompson](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/question/Who-was-Hunter-S-Thompson) | narration subjective, reportage embarque, caricature grotesque, vitesse et chaos controles |

Traduction tonale : le systeme peut etre decrit comme un road-trip technique hallucine, mais le log doit rester exploitable (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).18 Fantasy satirique

| Auteur | Source | Injection Mascarade |
|--------|--------|---------------------|
| Douglas Adams | [Britannica - Douglas Adams](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Douglas-Adams) | bureaucratie cosmique absurde, guide ironique, chance catastrophique, `42` |
| Terry Pratchett | [Britannica - Terry Pratchett](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Terry-Pratchett) | fantasy humoristique, monde-systeme satirique, tortue cosmique, institutions ridicules mais humaines |

Traduction tonale : Mascarade peut parler comme un manuel d'exploitation ecrit apres un passage entre Discworld et le Guide galactique (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).19 Axe philosophique

| Penseur | Source | Utilite dans le manifeste |
|---------|--------|---------------------------|
| Nietzsche | [SEP - Nietzsche's Aesthetics](https://plato (repo compagnon hors worktree).stanford (repo compagnon hors worktree).edu/archives/fall2025/entries/nietzsche-aesthetics/) | tension Apollon/Dionysos, joie tragique, art comme energie vitale |
| Gilles Deleuze | [SEP - Gilles Deleuze](https://plato (repo compagnon hors worktree).stanford (repo compagnon hors worktree).edu/archives/sum2022/entries/deleuze/) | difference, repetition, intensite, multiplicites |
| William James | [SEP - William James](https://plato (repo compagnon hors worktree).stanford (repo compagnon hors worktree).edu/archives/spr2004/entries/james/) | primat de l'experience vecue, mystique individuelle, verite par les effets |

Lecture de synthese : ordre operatoire apollinien, debordement dionysiaque, sensation deleuzienne, experience jamesienne (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).20 Noms satellites a garder en orbite

| Zone | Noms | Pourquoi les garder |
|------|------|---------------------|
| Beat / psych | [Ken Kesey](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Ken-Kesey), [Allen Ginsberg](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Allen-Ginsberg), [Jack Kerouac](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Jack-Kerouac), [Diane di Prima](https://poets (repo compagnon hors worktree).org/poet/diane-di-prima), [William S (repo compagnon hors worktree). Burroughs](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/William-S-Burroughs) | bus, prose spontanee, jazz, hallucination ecrite, cut-up, contre-culture, voix non academique |
| Gonzo visuel | [Hunter S (repo compagnon hors worktree). Thompson](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/question/Who-was-Hunter-S-Thompson), [Ralph Steadman](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Ralph-Steadman) | reportage sale, caricature grotesque, eclaboussures, humour agressif |
| Carnavalesque | [Mikhail Bakhtin](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Mikhail-Bakhtin) | polyphonie, grotesque, carnaval, foule, renversement des hierarchies |
| Fantasy / weird | [Ursula K (repo compagnon hors worktree). Le Guin](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Ursula-K-Le-Guin), [Michael Moorcock](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Michael-Moorcock), [Alejandro Jodorowsky](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Alejandro-Jodorowsky) | anthropologie des mondes, multivers, Loi/Chaos, tarot, alchimie, surralisme sacre |

Priorite de reinjection :
- Steadman si on veut plus de griffure visuelle et de grotesque (repo compagnon hors worktree).
- Bakhtin si on veut legitimer le cote carnaval/freaks (repo compagnon hors worktree).
- Le Guin si on veut plus de monde coherent et moins de pur delire (repo compagnon hors worktree).
- Moorcock si on veut pousser `multivers`, `champion`, `law vs chaos` (repo compagnon hors worktree).
- Kesey/Kerouac/Ginsberg/Burroughs si on veut plus de souffle beat et de vitesse verbale (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).21 Technopolitique, posthumanisme & corps

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Paul B (repo compagnon hors worktree). Preciado | [Bergen Assembly](https://2019 (repo compagnon hors worktree).bergenassembly (repo compagnon hors worktree).no/contributors/paul-b-preciado/), [steirischer herbst](https://2021 (repo compagnon hors worktree).steirischerherbst (repo compagnon hors worktree).at/en/program/artists/2106/paul-b-preciado) | biopolitique, genre comme technologie, corps sous regime mediatique et pharmacologique |
| Asma Mhalla | [Politika](https://www (repo compagnon hors worktree).politika (repo compagnon hors worktree).io/fr/entretien/politique-a-lere-numerique), [Les Rencontres Economiques](https://lesrencontreseconomiques (repo compagnon hors worktree).fr/2023/intervenants/asma-mhalla/) | souverainete techno, Big Tech comme puissance geopolitique, guerre hybride, citoyen-soldat numerique |
| Donna Haraway | [UCSC - Center for Cultural Studies](https://culturalstudies (repo compagnon hors worktree).ucsc (repo compagnon hors worktree).edu/2024/01/08/january-31-donna-haraway-making-kin-lynn-margulis-in-sympoiesis-with-sibling-scientists/), [CCCB](https://www (repo compagnon hors worktree).cccb (repo compagnon hors worktree).org/en/w/participants/donna-haraway) | cyborgs, savoirs situes, speculative fabulation, companion species, mondes hybrides |
| Rosi Braidotti | [Official bio](https://rosibraidotti (repo compagnon hors worktree).com/about/) | sujet nomade, posthuman feminism, intensite theorique sans retour au sujet stable |
| Ruha Benjamin | [Princeton](https://aas (repo compagnon hors worktree).princeton (repo compagnon hors worktree).edu/people/ruha-benjamin) | innovation et inequite, imagination liberatrice, critique de la technique dite neutre |
| Kate Crawford | [Microsoft Research](https://www (repo compagnon hors worktree).microsoft (repo compagnon hors worktree).com/en-us/research/people/kate/), [ANU School of Cybernetics](https://cybernetics (repo compagnon hors worktree).anu (repo compagnon hors worktree).edu (repo compagnon hors worktree).au/people/kate-crawford/) | IA comme infrastructure materielle, pouvoir calcule, extraction de travail et de ressources |
| N (repo compagnon hors worktree). Katherine Hayles | [American Academy of Arts and Sciences](https://www (repo compagnon hors worktree).amacad (repo compagnon hors worktree).org/person/n-katherine-hayles), [Duke Scholars](https://scholars (repo compagnon hors worktree).duke (repo compagnon hors worktree).edu/person/katherine (repo compagnon hors worktree).hayles) | posthumanisme litteraire, cognition distribuee, media et machines comme forme de pensee |
| Shoshana Zuboff | [Harvard Hillel](https://www (repo compagnon hors worktree).hillel (repo compagnon hors worktree).harvard (repo compagnon hors worktree).edu/oss-zuboff), [Penguin Random House](https://www (repo compagnon hors worktree).penguinrandomhouse (repo compagnon hors worktree).com/authors/244728/shoshana-zuboff/) | capitalisme de surveillance, capture comportementale, economie de prediction |

Lecture d'ensemble : si la premiere grappe donnait la couleur, celle-ci donne la structure de pouvoir (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).22 Media theory & acceleration critique

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Marshall McLuhan | [Britannica - Marshall McLuhan](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Marshall-McLuhan), [Estate of Marshall McLuhan](https://www (repo compagnon hors worktree).marshallmcluhan (repo compagnon hors worktree).com/biography/) | le medium comme environnement, pas simple canal; interfaces qui sculptent la perception |
| Paul Virilio | [Bloomsbury - Paul Virilio](https://www (repo compagnon hors worktree).bloomsbury (repo compagnon hors worktree).com/US/author/paul-virilio/) | vitesse, accident, logistique de la perception, guerre des ecrans |
| Bernard Stiegler | [IRI - About](https://www (repo compagnon hors worktree).iri (repo compagnon hors worktree).centrepompidou (repo compagnon hors worktree).fr/pied/about/), [Ars Industrialis - biography/bibliography](https://arsindustrialis (repo compagnon hors worktree).org/biographybibliography) | attention, pharmacologie des techniques, contribution contre simple consommation |
| McKenzie Wark | [CCCB - McKenzie Wark](https://www (repo compagnon hors worktree).cccb (repo compagnon hors worktree).org/en/w/participants/mckenzie-wark), [Penguin Random House - McKenzie Wark](https://www (repo compagnon hors worktree).penguinrandomhouse (repo compagnon hors worktree).com/authors/2067013/mckenzie-wark/) | hacker class, pouvoir vectorialiste, media studies transversales |
| Mark Fisher | [Repeater - Mark Fisher](https://repeaterbooks (repo compagnon hors worktree).com/authors/mark-fisher/) | hauntologie, futurs perdus, weird/eerie, melancolie politique branchee sur la culture pop |
| Franco "Bifo" Berardi | [CCCB - Franco Berardi](https://www (repo compagnon hors worktree).cccb (repo compagnon hors worktree).org/en/w/participants/franco-bifo-berardi), [MACBA - Franco Berardi](https://www (repo compagnon hors worktree).macba (repo compagnon hors worktree).cat/en/actor/franco-berardi/) | psychosphere, fatigue cognitive, medias autonomes, acceleration vecue comme epuisement |
| Kodwo Eshun | [MACBA - Kodwo Eshun](https://www (repo compagnon hors worktree).macba (repo compagnon hors worktree).cat/en/actor/kodwo-eshun/), [iniva - Kodwo Eshun](https://iniva (repo compagnon hors worktree).org/library/digital-archive/people/e/eshun-kodwo/) | sonic fiction, afrofuturisme, archives du futur, critique par le son et la fiction |

Regle d'usage : on prend ici une critique de l'acceleration et des milieux mediatiques, pas une devotion naive au "toujours plus vite" (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).23 Cyberfeminisme & glitch politics

| Figure / collectif | Source | Ce qu'on peut lui prendre |
|--------------------|--------|---------------------------|
| Sadie Plant | [Sadie Plant - biography](https://www (repo compagnon hors worktree).sadieplant (repo compagnon hors worktree).com/biography), [Sadie Plant - home](https://www (repo compagnon hors worktree).sadieplant (repo compagnon hors worktree).com/) | histoire alternative des technologies, cyberfeminisme des origines, `Zeros and Ones` |
| VNS Matrix | [transmediale - VNS Matrix](https://archive (repo compagnon hors worktree).transmediale (repo compagnon hors worktree).de/content/vns-matrix) | insolence cyberfeministe, sabotage symbolique du mainframe, manifeste comme virus |
| Legacy Russell | [Legacy Russell - Glitch Feminism](https://legacyrussell (repo compagnon hors worktree).com/filter/Glitch-Feminism), [Penguin Random House - Glitch Feminism](https://www (repo compagnon hors worktree).penguinrandomhouse (repo compagnon hors worktree).com/books/646946/glitch-feminism-by-legacy-russell/) | glitch comme liberation, corps/genre/tech en friction productive |
| Laboria Cuboniks | [Xenofeminism manifesto](https://laboriacuboniks (repo compagnon hors worktree).net/manifesto/xenofeminism-a-politics-for-alienation/) | anti-naturalisme, reingenierie, coalition, futur feministe en mode open source |

Pont avec 5 (repo compagnon hors worktree).21 : Haraway, Preciado, Braidotti et Russell/Plant/Cuboniks forment ensemble le versant "corps + code + fiction politique" (repo compagnon hors worktree).

### 5 (repo compagnon hors worktree).24 Occult tech & French theory

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Erik Davis | [Techgnosis - bio](https://techgnosis (repo compagnon hors worktree).com/about/bio/), [Harvard CSWR - Erik Davis](https://cswr (repo compagnon hors worktree).hds (repo compagnon hors worktree).harvard (repo compagnon hors worktree).edu/people/erik-davis) | mythe, magie, mysticisme et informatique; l'infrastructure a toujours un inconscient |
| Michel Foucault | [Britannica - Michel Foucault](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Michel-Foucault) | dispositifs, institutions, surveillance, verite comme production historique |
| Felix Guattari | [Britannica - Pierre-Felix Guattari](https://www (repo compagnon hors worktree).britannica (repo compagnon hors worktree).com/biography/Pierre-Felix-Guattari) | machines desirantes, revolutions moleculaires, ecologies mentales |
| Jean Baudrillard | [SEP - Jean Baudrillard](https://plato (repo compagnon hors worktree).stanford (repo compagnon hors worktree).edu/archives/spr2022/entries/baudrillard/) | simulation, signes autonomes, hyperreel, ecrans qui devorent le reel |

Lecture d'ensemble : French theory pour l'outillage critique; occult tech pour rappeler qu'aucune machine n'est purement rationnelle dans l'imaginaire collectif (repo compagnon hors worktree).

---

## 6 (repo compagnon hors worktree). Arborescence du repo

```
mascarade/
├── api/                    # API Hono (TypeScript)
├── core/                   # Orchestrateur LLM (Python)
├── skills/                 # Docs skills Mascarade
├── deploy/                 # Dockerfiles
├── docs/                   # Documentation ops
├── scripts/                # Scripts helpers
├── opt/                    # Migration /opt VM
│   ├── docker-studio-ai/   # Stack Docker complete (3 (repo compagnon hors worktree).8MB)
│   ├── llama (repo compagnon hors worktree).cpp/           # Ref + install script
│   └── skills-global/       # 124 skills categories + symlinks
├──  (repo compagnon hors worktree).claude/
│   └── skills/              # Skills projet (categories + _projects)
├── setup                    # Installateur TUI
├── docker-compose (repo compagnon hors worktree).yml       # Genere par setup
├── CLAUDE (repo compagnon hors worktree).md                # Conventions projet
└── MANIFEST (repo compagnon hors worktree).md              # Ce fichier
```

---

*mascarade v0 (repo compagnon hors worktree).1 (repo compagnon hors worktree).0 — photon-machine — 2026-03-04*
