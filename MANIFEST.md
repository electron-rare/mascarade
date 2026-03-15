# Mascarade — Manifest VM photon-machine

> **VM** : `photon-machine` — `192.168.0.119`
> **OS** : Photon OS (ESXi)
> **Date** : 2026-03-04
> **Signature** : *L'electron rare — unstable by design*

> Note:
> ce fichier est un snapshot machine/operator, pas une source de verite pour
> l'ownership des repos ni pour le chemin de release.
> Le contrat multi-repo actif est fige dans
> `/home/clems/crazy_life/docs/REPO_CARTOGRAPHY_2026-03-07.md`.

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

Constellation etendue liee aux nouvelles thematiques du manifeste :

| Compositeur / groupe | Source | Axe utile |
|----------------------|--------|-----------|
| Delia Derbyshire | [University of Manchester - Delia Derbyshire project](https://www.library.manchester.ac.uk/services/digitisation-services/projects/delia-derbyshire/index.htm), [Delia Derbyshire Day - archive](https://deliaderbyshireday.com/dd-archive/) | radiophonie, science-fiction sonore, bricolage magnetique, imagination DIY |
| Pauline Oliveros | [Pauline Oliveros Trust - about](https://www.paulineoliveros.us/about.html), [Center for Deep Listening - Pauline Oliveros](https://www.deeplistening.rpi.edu/deep-listening/pauline-oliveros/) | Deep Listening, attention elargie, rituel, ecoute collective, conscience sonore |
| Suzanne Ciani | [Suzanne Ciani - bio](https://www.sevwave.com/bio), [YBCA - Suzanne Ciani](https://ybca.org/artist/suzanne-ciani/) | Buchla, logos sonores, fluidite aquatique, synthese sensuelle, machine hospitaliere mais fantasque |
| Laurie Anderson | [Britannica - Laurie Anderson](https://www.britannica.com/biography/Laurie-Anderson) | voix, medias, ironie froide, performance techno-litteraire |
| Sun Ra | [NEA Jazz Masters - Sun Ra](https://www.arts.gov/honors/jazz/sun-ra) | afrofuturisme, cosmologie, freak orchestra, mythe spatial |
| Tangerine Dream | [Official website](https://www.tangerinedreammusic.com/) | sequencers, kosmische musik, voyage nocturne, fantasy synth, route cosmique |
| Ryoji Ikeda | [Official biography](https://www.ryojiikeda.com/biography/), [Arts at CERN - Ryoji Ikeda](https://arts.cern/artist/ryoji-ikeda/) | data, glitch, precision mathematique, lumiere froide, abstraction systemique |
| Annea Lockwood | [Official biography](https://www.annealockwood.com/biography/), [Fromm Foundation - Annea Lockwood](https://frommfoundation.fas.harvard.edu/people/annea-lockwood) | ecologie sonore, pianos rituels, paysages naturels, matiere acoustique brute |
| Terry Riley | [Cantaloupe Music - Terry Riley](https://cantaloupemusic.com/artists/terry-riley), [Bang on a Can - Terry Riley 90th Birthday Celebration](https://bangonacan.org/events/terry-riley-90th-birthday-celebration/) | repetition psychedelique, minimalisme extatique, boucle cosmique, transe joyeuse |

Raccourcis de reinjection :
- `Oliveros + Lockwood` pour l'ecoute, le rituel, l'environnement et la lenteur active.
- `Derbyshire + Ciani + Ikeda` pour machine, studio, signal, data et imaginaire techno.
- `Sun Ra + Tangerine Dream + Riley` pour cosmique, fantasy, route nocturne et trance.
- `Laurie Anderson` pour voix-off, medias, interface et sarcasme elegant.

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

### 5.15 Psychedelique, fantasy & freaks

Le manifeste assume maintenant une ligne esthetique plus explicite, avec un socle de references web documentees :

| Axe | Sources | Injection Mascarade |
|-----|---------|--------------------|
| Psychedelique | [Tate - Yayoi Kusama](https://shop.tate.org.uk/yayoi-kusama-infinity-mirror-room-purple-postcard/26132.html), [Tate - Gustav Metzger](https://shop.tate.org.uk/gustav-metzger-liquid-crystal-environment/radlan2206.html) | repetition, miroirs, lumiere, motifs obsessifs, couleurs mouvantes, plasma violet |
| Fantasy | [Britannica - fantasy](https://www.britannica.com/art/fantasy-narrative-genre), [The Met Cloisters - A Magical Menagerie](https://www.metmuseum.org/exhibitions/a-magical-menagerie) | autres mondes, etres surnaturels, bestiaire, portail opalin, grimoires de specs |
| Freaks | [Criterion - Freaks (1932)](https://www.criterion.com/films/29015-freaks) | carnaval mutant, troupe d'outsiders, freakshow de precision, compassion pour les marges |

Cette couche n'efface pas la rigueur technique. Elle sert de vernis narratif pour les CLIs, les FX, les easter eggs et la mythologie Mascarade.

- Ton cible : tech baroque, freakshow de precision, fantasy neon.
- Vocabulaire autorise : multivers, portail, glyphes, plasma, gobelins du build, bal des replicants.
- Contrainte implicite : garder le contraste entre chaos esthetique et execution propre.
- Raccourci de direction : Kusama pour l'immersion visuelle, Metzger pour la matiere mouvante, fantasy pour l'etrangete, Browning pour la troupe d'outsiders.

### 5.16 Canon psychedelique

| Figure | Source | Ce qui nourrit Mascarade |
|--------|--------|--------------------------|
| Timothy Leary | [Britannica - Timothy Leary](https://www.britannica.com/biography/Timothy-Leary) | expansion de conscience, contre-culture, rhetorique du basculement |
| Albert Hofmann | [Britannica - Albert Hofmann](https://www.britannica.com/biography/Albert-Hofmann) | laboratoire, perception alteree, discipline chimique, imaginaire du reveal |
| Aldous Huxley | [Britannica - Aldous Huxley](https://www.britannica.com/biography/Aldous-Huxley) | satire dystopique, vision, lucidite ironique, `The Doors of Perception` |
| Alexander Shulgin | [Shulgin Foundation - Archive](https://shulginfoundation.org/shulgin-archive/), [Purdue Archives](https://archives.lib.purdue.edu/agents/people/2485) | folklore du labo, precision documentaire, psychonautique ecrite comme catalogue et carnet |

Regle editoriale : on pioche ici une energie sensorielle et un imaginaire de l'experience, pas un manifeste d'usage.

### 5.17 Beat Generation & gonzo

| Courant | Source | Injection Mascarade |
|---------|--------|---------------------|
| Beat Generation | [Britannica - Beat movement](https://www.britannica.com/art/Beat-movement) | route, improvisation, prose qui pulse, fraternite d'outsiders |
| Gonzo journalism | [Britannica - gonzo journalism](https://www.britannica.com/topic/gonzo-journalism), [Britannica - Hunter S. Thompson](https://www.britannica.com/question/Who-was-Hunter-S-Thompson) | narration subjective, reportage embarque, caricature grotesque, vitesse et chaos controles |

Traduction tonale : le systeme peut etre decrit comme un road-trip technique hallucine, mais le log doit rester exploitable.

### 5.18 Fantasy satirique

| Auteur | Source | Injection Mascarade |
|--------|--------|---------------------|
| Douglas Adams | [Britannica - Douglas Adams](https://www.britannica.com/biography/Douglas-Adams) | bureaucratie cosmique absurde, guide ironique, chance catastrophique, `42` |
| Terry Pratchett | [Britannica - Terry Pratchett](https://www.britannica.com/biography/Terry-Pratchett) | fantasy humoristique, monde-systeme satirique, tortue cosmique, institutions ridicules mais humaines |

Traduction tonale : Mascarade peut parler comme un manuel d'exploitation ecrit apres un passage entre Discworld et le Guide galactique.

### 5.19 Axe philosophique

| Penseur | Source | Utilite dans le manifeste |
|---------|--------|---------------------------|
| Nietzsche | [SEP - Nietzsche's Aesthetics](https://plato.stanford.edu/archives/fall2025/entries/nietzsche-aesthetics/) | tension Apollon/Dionysos, joie tragique, art comme energie vitale |
| Gilles Deleuze | [SEP - Gilles Deleuze](https://plato.stanford.edu/archives/sum2022/entries/deleuze/) | difference, repetition, intensite, multiplicites |
| William James | [SEP - William James](https://plato.stanford.edu/archives/spr2004/entries/james/) | primat de l'experience vecue, mystique individuelle, verite par les effets |

Lecture de synthese : ordre operatoire apollinien, debordement dionysiaque, sensation deleuzienne, experience jamesienne.

### 5.20 Noms satellites a garder en orbite

| Zone | Noms | Pourquoi les garder |
|------|------|---------------------|
| Beat / psych | [Ken Kesey](https://www.britannica.com/biography/Ken-Kesey), [Allen Ginsberg](https://www.britannica.com/biography/Allen-Ginsberg), [Jack Kerouac](https://www.britannica.com/biography/Jack-Kerouac), [Diane di Prima](https://poets.org/poet/diane-di-prima), [William S. Burroughs](https://www.britannica.com/biography/William-S-Burroughs) | bus, prose spontanee, jazz, hallucination ecrite, cut-up, contre-culture, voix non academique |
| Gonzo visuel | [Hunter S. Thompson](https://www.britannica.com/question/Who-was-Hunter-S-Thompson), [Ralph Steadman](https://www.britannica.com/biography/Ralph-Steadman) | reportage sale, caricature grotesque, eclaboussures, humour agressif |
| Carnavalesque | [Mikhail Bakhtin](https://www.britannica.com/biography/Mikhail-Bakhtin) | polyphonie, grotesque, carnaval, foule, renversement des hierarchies |
| Fantasy / weird | [Ursula K. Le Guin](https://www.britannica.com/biography/Ursula-K-Le-Guin), [Michael Moorcock](https://www.britannica.com/biography/Michael-Moorcock), [Alejandro Jodorowsky](https://www.britannica.com/biography/Alejandro-Jodorowsky) | anthropologie des mondes, multivers, Loi/Chaos, tarot, alchimie, surralisme sacre |

Priorite de reinjection :
- Steadman si on veut plus de griffure visuelle et de grotesque.
- Bakhtin si on veut legitimer le cote carnaval/freaks.
- Le Guin si on veut plus de monde coherent et moins de pur delire.
- Moorcock si on veut pousser `multivers`, `champion`, `law vs chaos`.
- Kesey/Kerouac/Ginsberg/Burroughs si on veut plus de souffle beat et de vitesse verbale.

### 5.21 Technopolitique, posthumanisme & corps

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Paul B. Preciado | [Bergen Assembly](https://2019.bergenassembly.no/contributors/paul-b-preciado/), [steirischer herbst](https://2021.steirischerherbst.at/en/program/artists/2106/paul-b-preciado) | biopolitique, genre comme technologie, corps sous regime mediatique et pharmacologique |
| Asma Mhalla | [Politika](https://www.politika.io/fr/entretien/politique-a-lere-numerique), [Les Rencontres Economiques](https://lesrencontreseconomiques.fr/2023/intervenants/asma-mhalla/) | souverainete techno, Big Tech comme puissance geopolitique, guerre hybride, citoyen-soldat numerique |
| Donna Haraway | [UCSC - Center for Cultural Studies](https://culturalstudies.ucsc.edu/2024/01/08/january-31-donna-haraway-making-kin-lynn-margulis-in-sympoiesis-with-sibling-scientists/), [CCCB](https://www.cccb.org/en/w/participants/donna-haraway) | cyborgs, savoirs situes, speculative fabulation, companion species, mondes hybrides |
| Rosi Braidotti | [Official bio](https://rosibraidotti.com/about/) | sujet nomade, posthuman feminism, intensite theorique sans retour au sujet stable |
| Ruha Benjamin | [Princeton](https://aas.princeton.edu/people/ruha-benjamin) | innovation et inequite, imagination liberatrice, critique de la technique dite neutre |
| Kate Crawford | [Microsoft Research](https://www.microsoft.com/en-us/research/people/kate/), [ANU School of Cybernetics](https://cybernetics.anu.edu.au/people/kate-crawford/) | IA comme infrastructure materielle, pouvoir calcule, extraction de travail et de ressources |
| N. Katherine Hayles | [American Academy of Arts and Sciences](https://www.amacad.org/person/n-katherine-hayles), [Duke Scholars](https://scholars.duke.edu/person/katherine.hayles) | posthumanisme litteraire, cognition distribuee, media et machines comme forme de pensee |
| Shoshana Zuboff | [Harvard Hillel](https://www.hillel.harvard.edu/oss-zuboff), [Penguin Random House](https://www.penguinrandomhouse.com/authors/244728/shoshana-zuboff/) | capitalisme de surveillance, capture comportementale, economie de prediction |

Lecture d'ensemble : si la premiere grappe donnait la couleur, celle-ci donne la structure de pouvoir.

### 5.22 Media theory & acceleration critique

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Marshall McLuhan | [Britannica - Marshall McLuhan](https://www.britannica.com/biography/Marshall-McLuhan), [Estate of Marshall McLuhan](https://www.marshallmcluhan.com/biography/) | le medium comme environnement, pas simple canal; interfaces qui sculptent la perception |
| Paul Virilio | [Bloomsbury - Paul Virilio](https://www.bloomsbury.com/US/author/paul-virilio/) | vitesse, accident, logistique de la perception, guerre des ecrans |
| Bernard Stiegler | [IRI - About](https://www.iri.centrepompidou.fr/pied/about/), [Ars Industrialis - biography/bibliography](https://arsindustrialis.org/biographybibliography) | attention, pharmacologie des techniques, contribution contre simple consommation |
| McKenzie Wark | [CCCB - McKenzie Wark](https://www.cccb.org/en/w/participants/mckenzie-wark), [Penguin Random House - McKenzie Wark](https://www.penguinrandomhouse.com/authors/2067013/mckenzie-wark/) | hacker class, pouvoir vectorialiste, media studies transversales |
| Mark Fisher | [Repeater - Mark Fisher](https://repeaterbooks.com/authors/mark-fisher/) | hauntologie, futurs perdus, weird/eerie, melancolie politique branchee sur la culture pop |
| Franco "Bifo" Berardi | [CCCB - Franco Berardi](https://www.cccb.org/en/w/participants/franco-bifo-berardi), [MACBA - Franco Berardi](https://www.macba.cat/en/actor/franco-berardi/) | psychosphere, fatigue cognitive, medias autonomes, acceleration vecue comme epuisement |
| Kodwo Eshun | [MACBA - Kodwo Eshun](https://www.macba.cat/en/actor/kodwo-eshun/), [iniva - Kodwo Eshun](https://iniva.org/library/digital-archive/people/e/eshun-kodwo/) | sonic fiction, afrofuturisme, archives du futur, critique par le son et la fiction |

Regle d'usage : on prend ici une critique de l'acceleration et des milieux mediatiques, pas une devotion naive au "toujours plus vite".

### 5.23 Cyberfeminisme & glitch politics

| Figure / collectif | Source | Ce qu'on peut lui prendre |
|--------------------|--------|---------------------------|
| Sadie Plant | [Sadie Plant - biography](https://www.sadieplant.com/biography), [Sadie Plant - home](https://www.sadieplant.com/) | histoire alternative des technologies, cyberfeminisme des origines, `Zeros and Ones` |
| VNS Matrix | [transmediale - VNS Matrix](https://archive.transmediale.de/content/vns-matrix) | insolence cyberfeministe, sabotage symbolique du mainframe, manifeste comme virus |
| Legacy Russell | [Legacy Russell - Glitch Feminism](https://legacyrussell.com/filter/Glitch-Feminism), [Penguin Random House - Glitch Feminism](https://www.penguinrandomhouse.com/books/646946/glitch-feminism-by-legacy-russell/) | glitch comme liberation, corps/genre/tech en friction productive |
| Laboria Cuboniks | [Xenofeminism manifesto](https://laboriacuboniks.net/manifesto/xenofeminism-a-politics-for-alienation/) | anti-naturalisme, reingenierie, coalition, futur feministe en mode open source |

Pont avec 5.21 : Haraway, Preciado, Braidotti et Russell/Plant/Cuboniks forment ensemble le versant "corps + code + fiction politique".

### 5.24 Occult tech & French theory

| Figure | Source | Ce qu'on peut lui prendre |
|--------|--------|---------------------------|
| Erik Davis | [Techgnosis - bio](https://techgnosis.com/about/bio/), [Harvard CSWR - Erik Davis](https://cswr.hds.harvard.edu/people/erik-davis) | mythe, magie, mysticisme et informatique; l'infrastructure a toujours un inconscient |
| Michel Foucault | [Britannica - Michel Foucault](https://www.britannica.com/biography/Michel-Foucault) | dispositifs, institutions, surveillance, verite comme production historique |
| Felix Guattari | [Britannica - Pierre-Felix Guattari](https://www.britannica.com/biography/Pierre-Felix-Guattari) | machines desirantes, revolutions moleculaires, ecologies mentales |
| Jean Baudrillard | [SEP - Jean Baudrillard](https://plato.stanford.edu/archives/spr2022/entries/baudrillard/) | simulation, signes autonomes, hyperreel, ecrans qui devorent le reel |

Lecture d'ensemble : French theory pour l'outillage critique; occult tech pour rappeler qu'aucune machine n'est purement rationnelle dans l'imaginaire collectif.

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
