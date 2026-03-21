# Skills Architecture Analysis

## Current State: Two Parallel Systems

### V1 — AgentRegistry + Agent dataclass

- **Registry**: `AgentRegistry` in `registry.py`
- **Data model**: `Agent` dataclass in `base.py`
- **Storage**: `data/agents.json`
- **API**: `/api/agents` (CRUD + `/run` + `/metrics`) in `routers/agents.py`
- **Init**: `register_default_skills(registry)` creates `Agent` objects + specialized subclasses (FreeCADAgent, SpiceAgent, KiCadAgent, ComponentsAgent)

**Agent fields**: name, description, system_prompt, preferred_provider, preferred_model, preferred_role, strategy, routing_policy, tools, temperature, max_tokens, skills (list of skill names), retry_config, prompt_versions

**Extra capabilities**:
- Prompt versioning with diff tracking on save
- Metrics tracking (via `MetricsTracker`)
- `run()` / `run_with_history()` — can actually execute LLM calls via Router
- `get_enhanced_system_prompt(skill_registry)` — merges base prompt with assigned Skill instructions
- Specialized Agent subclasses for domain tools

### V2 — SkillRegistry + Skill dataclass

- **Registry**: `SkillRegistry` in `skill_registry.py`
- **Data model**: `Skill` dataclass in `skill.py`
- **Storage**: `data/skills.json`
- **API**: `/api/skills` (CRUD + assign/unassign to agents) in `routers/skills.py`
- **Init**: `register_default_skills_v2(skill_registry)` converts each `ALL_SKILLS` Agent into a `Skill`

**Skill fields**: name, description, category, instruction, tools, examples, enabled, version

**Extra capabilities**:
- Category system (text, code, analysis, creative, domain, coordination)
- Enable/disable toggle
- Few-shot examples slot
- Assign/unassign to agents (modifies `Agent.skills` list)

---

## Key Differences

| Aspect | AgentRegistry (v1) | SkillRegistry (v2) |
|---|---|---|
| Data model | `Agent` — full execution unit | `Skill` — composable instruction fragment |
| Can execute LLM calls | Yes (`agent.run()`) | No (injected into Agent context) |
| Metrics | Yes (MetricsTracker) | No |
| Prompt versioning | Yes (diff on save) | No |
| Categories | No | Yes |
| Enable/disable | No | Yes (`.enabled`) |
| Few-shot examples | No | Yes (`.examples`, unused) |
| Specialized subclasses | Yes (FreeCAD, SPICE, KiCad, Components) | No |
| Persistence | Atomic JSON write | Atomic JSON write (identical pattern) |

---

## Redundancy Analysis

### High redundancy
1. **Same builtin definitions registered twice**: `register_default_skills()` and `register_default_skills_v2()` both iterate `ALL_SKILLS` and create parallel entries. Every builtin agent exists as both an Agent and a Skill with the same name, description, and system prompt.
2. **Registry code is 90% identical**: `SkillRegistry` is a copy-paste of `AgentRegistry` with `Agent` replaced by `Skill`, minus metrics and prompt versioning.
3. **Both stored in `app.state`**: `app.state.registry` (AgentRegistry) and `app.state.skill_registry` (SkillRegistry) coexist.

### Conceptual gap
The intended design is a **composition model**: Skills are instruction fragments that agents can compose via `Agent.skills` list + `get_enhanced_system_prompt()`. However:
- `get_enhanced_system_prompt()` is **never called** in the orchestrator, chat router, or any execution path. The skill composition feature is wired but not used at runtime.
- The `/api/skills/.../assign/{agent}` endpoints modify `Agent.skills`, but no execution path reads the enhanced prompt.

### What actually runs
- The orchestrator and chat router use `AgentRegistry` exclusively.
- `SkillRegistry` is only consumed by `routers/skills.py` for CRUD operations. It is a data store with no runtime effect on LLM calls.

---

## Recommendation: Unify into a Single System

### Target architecture

Keep **one registry** (`AgentRegistry`) and **one data model** (`Agent`), but absorb the useful v2 concepts:

1. **Add to Agent dataclass**: `category: str`, `enabled: bool`, `examples: list[dict]` (from Skill)
2. **Remove Skill dataclass and SkillRegistry entirely** — they add no runtime value
3. **Merge the APIs**: The `/api/skills` endpoints become category/metadata management on agents, or are removed
4. **Wire `get_enhanced_system_prompt()`** in the orchestrator if skill composition is actually desired — otherwise remove the dead code

### Alternative: Keep Skills as composable fragments

If the composition model (agents that combine multiple skill instructions) is the long-term goal:
1. Keep `Skill` as a lightweight fragment (instruction + tools + examples)
2. Remove the duplicate builtin registration — skills should NOT mirror agents 1:1
3. Actually use `get_enhanced_system_prompt()` in the execution path
4. Skills become add-ons (e.g. "json-output-format", "safety-guardrails"), not clones of agents

---

## Migration Plan (Option A: Merge into Agent)

### Phase 1 — Add missing fields to Agent
- Add `category`, `enabled`, `examples` fields to `Agent` dataclass
- Update `AgentCreate`/`AgentUpdate` Pydantic models
- Update serialization

### Phase 2 — Migrate skill-specific endpoints
- Move `/api/skills` CRUD logic into `/api/agents` (or keep as alias)
- Remove assign/unassign endpoints (no longer needed — agents are self-contained)

### Phase 3 — Remove v2 artifacts
- Delete `skill.py`, `skill_registry.py`
- Remove `register_default_skills_v2()` from `skills.py`
- Remove `skill_registry` from `server.py` lifespan
- Remove `routers/skills.py`
- Update `__init__.py`

### Phase 4 — Clean up dead code
- Evaluate `get_enhanced_system_prompt()` — either wire it into orchestrator or remove it
- Remove `_AGENT_CATEGORY_MAP` (category now lives on Agent)

## Migration Plan (Option B: Keep Skills as composable fragments)

### Phase 1 — Decouple Skills from Agents
- Remove the 1:1 mirroring in `register_default_skills_v2()`
- Create actual composable skills (e.g. "json-output", "concise-mode", "safety-check")
- Skills should be orthogonal to agents, not duplicates

### Phase 2 — Wire composition into runtime
- Call `get_enhanced_system_prompt(skill_registry)` in orchestrator/chat execution paths
- Pass skill_registry to `agent.run()` so the enhanced prompt is used

### Phase 3 — Simplify registry code
- Extract a generic `BaseRegistry[T]` to eliminate the copy-paste between AgentRegistry and SkillRegistry

---

## Files Involved

| File | Role |
|---|---|
| `agents/base.py` | Agent dataclass |
| `agents/skill.py` | Skill dataclass (v2) |
| `agents/registry.py` | AgentRegistry (v1) |
| `agents/skill_registry.py` | SkillRegistry (v2) |
| `agents/skills.py` | Builtin definitions + both register functions |
| `agents/__init__.py` | Public exports |
| `routers/agents.py` | Agent API endpoints |
| `routers/skills.py` | Skill API endpoints (v2) |
| `server.py` | Lifespan — initializes both registries |
