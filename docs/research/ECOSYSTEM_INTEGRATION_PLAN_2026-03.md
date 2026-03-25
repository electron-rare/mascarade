# Plan d'intégration écosystème — Mascarade × Kill_LIFE × Projets créatifs

_2026-03-25_

## Vue d'ensemble de l'écosystème

```
┌─────────────────────────────────────────────────────────┐
│                    MASCARADE (hub)                        │
│  25+ providers · 35 agents · P2P mesh · MCP · A2A        │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│ Kill_LIFE│ crazy_life│ er-ops   │ai-novel  │ kxkm_clown  │
│ control  │ cockpit  │ ops dash │ engine   │ multimodal   │
│ plane    │ workflow │ kanban   │ writing  │ chat+audio   │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│ mascarade_box-S3 · 1-KXKM · HLabs · Fauteuil · LEDs    │
│           Hardware / Embedded / IoT                       │
└─────────────────────────────────────────────────────────┘
```

---

## Intégrations par projet

### 1. MASCARADE (core orchestration)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **LiteLLM** | Remplacer 25+ providers custom par 1 abstraction | P0 | `pip install litellm`, adapter Router._register_defaults() |
| **Langfuse** | Observabilité complète (traces, coûts, evals) | P0 | Docker self-hosted, decorator `@observe()` sur agents |
| **OpenLLMetry** | Auto-instrumentation OTel pour tous providers | P1 | `Traceloop.init()` dans server.py startup |
| **MCP Python SDK** | Remplacer MCP custom par SDK officiel | P1 | Migrer mcp/server.py vers `mcp` package |
| **python-a2a** | Standardiser A2A sur protocole Google | P1 | Remplacer routers/a2a.py custom |
| **RouteLLM** | ML routing formalisé | P2 | Intégrer comme Strategy.ROUTELLM backend |
| **GPTCache** | Upgrade cache L3 sémantique | P2 | Remplacer semantic_cache.py |

### 2. KILL_LIFE (control plane)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **LangGraph** | DAG d'exécution pour spec-first pipeline | P1 | Remplacer lot_chain par LangGraph graphs |
| **CrewAI** | BMAD agents (7 rôles) comme CrewAI crews | P1 | Mapper Agent Zero → CrewAI Manager |
| **Langfuse** | Tracer le pipeline lot_chain end-to-end | P1 | Instrumenter via Mascarade |
| **MCP Registry** | Découverte dynamique des outils | P2 | Kill_LIFE MCP tools enregistrés |

### 3. AI-NOVEL-ENGINE (creative writing)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **Book Series MCP** | Suivi personnages/intrigues/monde | P0 | Connecter comme MCP server |
| **Writer MCP** | Knowledge base par personnage | P1 | Compléter le pipeline ANE |
| **NovelGenerator** | Référence pipeline premise→EPUB | P2 | Étudier architecture multi-agent |
| **Qwen3-14B** | Modèle cost-efficient pour drafts | P1 | Via Mascarade routing CHEAPEST |
| **Qwen3-235B** | Modèle qualité pour rewrite/gate | P1 | Via Mascarade routing BEST |

### 4. KXKM_CLOWN (multimodal chat)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **Reaper MCP** | Contrôle DAW natif pour les 19 backends audio | P0 | Connecter comme MCP server |
| **MiniMax/Suno MCP** | Text-to-music pour les personas | P1 | Ajouter comme MCP tool |
| **music21 MCP** | Analyse musicale | P2 | Pour le persona musicien |
| **LacyLights MCP** | Contrôle DMX pour spectacles | P1 | Via Mascarade Node Engine |

### 5. HARDWARE (mascarade_box-S3, KXKM, HLabs)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **KiCad MCP (Seeed)** | 39 tools KiCad via MCP (le plus complet) | P0 | Remplacer kicad_servers.py custom |
| **kicad-happy** | Skills Claude Code pour KiCad | P1 | Porter comme agents Mascarade |
| **FreeCAD MCP (neka-nat)** | Contrôle FreeCAD via MCP | P1 | Remplacer freecad intégration custom |
| **circuit-synth** | Manipulation schématiques | P2 | Intégrer dans SPICE agent |
| **pcb-designer-ai** | ML placement/routing PCB | P2 | Exposer comme Mascarade agent |

### 6. ER-OPS + CRAZY_LIFE (dashboards)

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **Langfuse UI** | Dashboard observabilité intégré | P1 | Embed dans er-ops (iframe ou API) |
| **OpenLIT dashboard** | GPU monitoring pour la VM | P2 | Complément Grafana |

### 7. INFRASTRUCTURE P2P

| Lib | Impact | Priorité | Action |
|-----|--------|----------|--------|
| **Exo** | Cluster Apple Silicon (MLX, ring topology) | P1 | Déjà provider, formaliser le cluster |
| **llm-d** | Kubernetes-native disaggregated inference | P2 | Pour scale-out futur |
| **LocalAI** | MCP apps + P2P via MLX | P2 | Alternative à Ollama |

---

## Matrice de priorités globale

### P0 — Cette semaine
1. **LiteLLM** dans Mascarade (réduire dette maintenance providers)
2. **Langfuse** self-hosted sur VM (observabilité immédiate)
3. **Seeed KiCad MCP** (39 tools > notre implémentation custom)
4. **Book Series MCP** pour ai-novel-engine
5. **Reaper MCP** pour kxkm_clown

### P1 — Ce mois
6. MCP Python SDK (migration officielle)
7. python-a2a (protocole Google)
8. OpenLLMetry (auto-instrumentation)
9. CrewAI pour Kill_LIFE BMAD agents
10. LangGraph pour Kill_LIFE lot_chain
11. FreeCAD MCP + kicad-happy skills

### P2 — Prochain trimestre
12. GPTCache semantic cache
13. RouteLLM formalisé
14. OpenLIT GPU monitoring
15. llm-d pour scale-out
16. pcb-designer-ai ML routing

---

## Gains estimés

| Intégration | Lignes de code éliminées | Fonctionnalité gagnée |
|-------------|--------------------------|----------------------|
| LiteLLM | ~3000 LOC (25 providers) | 200+ providers, cost tracking automatique |
| Langfuse | ~500 LOC (observability custom) | Traces, evals, prompt management UI |
| MCP Python SDK | ~800 LOC (mcp/server.py) | Conformité spec officielle |
| Seeed KiCad MCP | ~400 LOC (kicad_servers.py) | 39 tools vs nos ~10 |
| python-a2a | ~200 LOC (routers/a2a.py) | Conformité Google A2A |
| **Total** | **~5000 LOC éliminées** | **Maintenance ÷ 5** |
