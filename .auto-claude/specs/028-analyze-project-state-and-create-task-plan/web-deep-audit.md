# Web React Deep Code Audit

## Scope

Deep audit of 5 pages exceeding 1,000 lines: Logs.tsx (1,468), Settings.tsx (1,129), OpsHub.tsx (1,092), Orchestrate.tsx (1,028), KillLifeWorkflowEditor.tsx (1,019).

---

## 1. Page-by-Page Decomposition Analysis

### 1.1 Logs.tsx (1,468 lines) — HIGHEST PRIORITY

**Structure:** 1 default export (~700 lines JSX) + 24 helper functions + constants.

**Helper functions (24):**
`formatStamp`, `severityClasses`, `sourceBadgeTone`, `traceTone`, `nonEmptyLabel`, `pickOptionValue`, `normalizeFilter`, `matchesRoutingLabels`, `matchesRoutingEntry`, `matchesRoutingTraceEvent`, `sourceTone`, `mcpTone`, `formatLatency`, `formatRoutingLatency`, `formatMcpName`, `summarizeMcpServer`, `severityRank`, `mergeLiveEntries`, `parseEventPayload` + 5 option arrays.

**State:** 12+ `useState`, 3 `useRef`, 4+ `useMemo`, 2+ `useEffect`, multiple `useFetch`.

**Proposed decomposition (6 components):**

| Component | Lines | Responsibility |
|-----------|-------|---------------|
| `LogsFilterBar` | ~120 | 12+ filter inputs (severity, source, role, provider, model) |
| `LogsStatsRow` | ~50 | 5 stat cards (total, errors, warnings, sources, latency) |
| `LogsLiveHeader` | ~100 | Title, status badges, pause/resume, mode toggle |
| `TraceDetail` | ~150 | Run detail panel with event timeline |
| `McpStatusWidget` | ~100 | MCP servers grid with status badges |
| `IncidentPresets` | ~90 | Quick-access preset filter buttons |

**Result:** Main Logs component drops from ~700 to ~200 lines.

---

### 1.2 Settings.tsx (1,129 lines)

**Structure:** 3 exported components + 5 helper functions/sub-components.

**Components:**
- `Settings` (default, ~180 lines) — orchestrator
- `ProviderCard` (~350 lines) — provider configuration form
- `RuntimeSecretCard` (~390 lines) — runtime secret configuration form
- `CriticalityChip`, `MetaLine`, `StatusBadge`, `RuntimeBadge` — small display components

**State per card:** 4 `useState`, 1 `useRef` (timer), 1 `useCallback`.

**Key issue:** ProviderCard and RuntimeSecretCard share ~80% identical logic (draft management, save/settle pattern, timer cleanup, field rendering). This is the strongest DRY violation in the web codebase.

**Proposed decomposition:**

| Component | Lines | Responsibility |
|-----------|-------|---------------|
| `useSettleNotification` | ~30 | Custom hook: timer-based save state reset (extract from both cards) |
| `SecretFieldEditor` | ~80 | Shared field input with reveal/save logic |
| `SettingsSummary` | ~50 | Summary cards at top of page |
| `ProvidersList` | ~30 | Grid wrapper for provider cards |
| `RuntimeSecretsList` | ~30 | Grid wrapper for runtime secret cards |

**Result:** ProviderCard and RuntimeSecretCard each drop ~100 lines via shared hook + field editor.

---

### 1.3 OpsHub.tsx (1,092 lines)

**Structure:** 1 default export (~600 lines JSX) + 15 helper functions.

**Helper functions (15):**
`statusTone`, `chipTone`, `formatLatency`, `shortUrl`, `sourceTone`, `alertTone`, `logSourceTone`, `mcpTone`, `formatMcpName`, `formatChecks`, `summarizeMcpServer`, `industrialServerStats`, `summarizeIndustrialServer`, `findPublicSurface`.

**State:** 4 `useFetch` (with polling), 3 `useMemo`, 1 `useApi`.

**Key issue:** ~100-line `useMemo` for links array with 20+ conditional entries. Large monolithic JSX with deeply nested structure.

**Proposed decomposition (6 components):**

| Component | Lines | Responsibility |
|-----------|-------|---------------|
| `OpsHubHeader` | ~80 | Title, overall status, refresh button |
| `ServiceHealthGrid` | ~100 | Individual service health cards |
| `PublicSurfaceLinks` | ~150 | External service links list |
| `McpServersPanel` | ~150 | MCP server status grid (shared with Logs) |
| `AlertsPanel` | ~80 | Active alerts display |
| `IndustrialPanel` | ~80 | Industrial server stats |

**Result:** Main OpsHub drops from ~600 to ~200 lines.

---

### 1.4 Orchestrate.tsx (1,028 lines)

**Structure:** 1 default export (~600 lines) + 8 helpers + constants/types.

**State:** 15+ `useState`, 5+ `useMemo`, 1 `useFetch`, 1 `useApi`.

**Key issue:** Highest useState count of any page. Complex derived state chains (8+ memos). No handler memoization — every render creates new closures for toggleAgent, handleRun, handleCadAction.

**Proposed decomposition (6 components):**

| Component | Lines | Responsibility |
|-----------|-------|---------------|
| `AgentSelector` | ~150 | Agent list with checkboxes and cluster grouping |
| `RoutingOverrideForm` | ~100 | Per-agent routing policy/model overrides |
| `RunPromptBar` | ~80 | Prompt input + preset selection |
| `TraceViewer` | ~150 | Trace event timeline with filtering |
| `CadPanel` | ~100 | FreeCAD/OpenSCAD integration controls |
| `McpFilterBar` | ~60 | MCP server/tool/status filtering |

**Result:** Main Orchestrate drops from ~600 to ~200 lines.

---

### 1.5 KillLifeWorkflowEditor.tsx (1,019 lines)

**Structure:** 1 default export (~600 lines) + 11 helper functions + constants.

**Helpers:** `cloneWorkflow`, `formatDate`, `durationLabel`, `statusColor`, `nodeTone`, `defaultRunner`, `nextNodeId`, `nextEdgeId`, `autoLayout`.

**State:** 10 `useState`, 3 `useRef`, 3 `useMemo`, 4 `useEffect`, 3 `useApi`.

**Key issue:** Canvas drag handling with manual event listener management in useEffect. JSON.stringify cloning on every state update.

**Proposed decomposition (8 components):**

| Component | Lines | Responsibility |
|-----------|-------|---------------|
| `WorkflowCanvas` | ~150 | SVG canvas + edge rendering + pan/zoom |
| `WorkflowNode` | ~60 | Individual node button on canvas |
| `NodeInspector` | ~200 | Selected node editor panel |
| `WorkflowToolbar` | ~50 | Save/validate/run action buttons |
| `ValidationPanel` | ~80 | Validation errors display |
| `EvidencePanel` | ~100 | Evidence browsing for selected node |
| `RunsHistory` | ~100 | Recent workflow runs list |
| `WorkflowStats` | ~30 | Node/edge count badges |

**Result:** Main editor drops from ~600 to ~150 lines.

---

## 2. Shared Component Extraction Opportunities

### 2.1 Duplicated Utility Functions (CRITICAL — extract to `lib/formatting.ts`)

| Function | Files | Copies | Variation |
|----------|-------|--------|-----------|
| `formatLatency()` | Logs, OpsHub, Orchestrate | 3 | Minor null-safety diffs |
| `formatMcpName()` | Logs, OpsHub | 2 | Identical |
| `mcpTone()` | Logs, OpsHub | 2 | Identical |
| `sourceTone()` | Logs, OpsHub | 2 | Identical |
| `summarizeMcpServer()` | Logs, OpsHub | 2 | Slightly different output |

**Recommendation:** Create `web/src/lib/formatting.ts` with all shared formatting/tone functions. Estimated: ~80 lines, eliminates ~200 lines of duplication.

### 2.2 Shared UI Patterns (extract to components)

| Pattern | Files | Proposed Component |
|---------|-------|--------------------|
| MCP server status grid | Logs, OpsHub | `McpServersPanel` |
| Save/settle notification | Settings (×2) | `useSettleNotification` hook |
| Severity badge rendering | Logs, OpsHub | Already using `Badge` — standardize tone mapping |
| Stat card rows | Logs, OpsHub, Dashboard | Already using `StatCard` — increase adoption |

---

## 3. State Management Patterns

### Pattern inventory across all 5 pages:

| Pattern | Usage | Assessment |
|---------|-------|------------|
| `useState` | 49+ total hooks | Appropriate for local UI state |
| `useFetch` (custom) | 12 instances with polling | Good abstraction, well-used |
| `useApi` (custom) | 6 instances | Good for mutations |
| `useMemo` | 17+ instances | Adequate but some missing (see anti-patterns) |
| `useEffect` | 11+ instances | Some could be replaced with event handlers |
| `useRef` | 7 instances | Appropriate uses (timers, DOM, dedup sets) |
| `useReducer` | 0 | **Missing** — Orchestrate (15 states) and KillLife (10 states) should use reducers |
| Context | Only AuthContext | Appropriate — no prop drilling detected |

### Recommendations:
1. **Orchestrate.tsx:** Replace 15 `useState` with `useReducer` for routing/filter state
2. **KillLifeWorkflowEditor.tsx:** Replace workflow + selection state with `useReducer`
3. **Settings.tsx:** Extract shared timer/settle logic into custom hook

---

## 4. Performance Anti-Patterns

### 4.1 Missing Memoization (HIGH impact)

| Page | Issue | Fix |
|------|-------|-----|
| Orchestrate | `toggleAgent`, `handleRun`, `handleCadAction` recreated every render | Wrap in `useCallback` |
| Logs | Live feed `.filter()` chains in render path | Memoize filtered results |
| OpsHub | 20+ conditional link objects in `useMemo` with repeated `findPublicSurface` calls | Cache surface lookups |
| KillLife | Node `.map()` rendering without keys or memo | Extract `WorkflowNode` with `React.memo` |

### 4.2 Expensive Operations in Render (MEDIUM impact)

| Page | Issue | Fix |
|------|-------|-----|
| KillLife | `JSON.parse(JSON.stringify(workflow))` on every state change | Use `structuredClone()` or immer |
| Orchestrate | Multiple `Array.from(new Set(...))` in useMemo chains | Consolidate into single pass |
| Logs | `mergeLiveEntries` runs on every WebSocket message without batching | Batch with requestAnimationFrame |

### 4.3 Bundle Size Concerns (LOW impact)

- **No lazy loading:** All 18 pages eagerly imported in App.tsx
- **Monaco Editor** (used in Playground, KillLife): ~2MB, loaded for all users
- **Recommendation:** `React.lazy()` + `Suspense` for pages behind navigation, especially Monaco-dependent pages

### 4.4 Inline Object/Function Creation (LOW impact)

| Page | Count | Example |
|------|-------|---------|
| Logs | 6+ | Inline className arrays in `.join(" ")` |
| OpsHub | 8+ | Inline style objects in conditional rendering |
| Settings | 4+ | Inline callbacks in `.map()` |

---

## 5. Test Gap Assessment

**Current state: ZERO tests across the entire web service.**

### Priority test targets (by risk × complexity):

| Priority | Component | Test Type | Rationale |
|----------|-----------|-----------|-----------|
| P0 | `useFetch` hook | Unit | Used by 12+ pages, polling logic |
| P0 | `useApi` hook | Unit | Used for all mutations |
| P0 | `AuthContext` | Unit | Auth flow correctness |
| P1 | Formatting utilities | Unit | Pure functions, easy to test |
| P1 | `Logs` filter logic | Unit | Complex filter chains |
| P2 | `KillLife` workflow state | Integration | Complex state machine |
| P2 | `Settings` save flow | Integration | API interaction |

---

## 6. Summary

### By severity:

| Severity | Count | Key Items |
|----------|-------|-----------|
| CRITICAL | 2 | Zero test coverage; 5 pages >1000 lines with no decomposition |
| HIGH | 3 | 200+ lines duplicated utilities; Settings DRY violation; no lazy loading |
| MEDIUM | 4 | Missing useCallback/memo; JSON cloning; no useReducer for complex state |
| LOW | 3 | Inline objects; className concatenation; French comments |

### Estimated effort for full remediation:

| Action | Effort | Impact |
|--------|--------|--------|
| Extract `lib/formatting.ts` | 2h | Eliminates 200 lines duplication |
| Decompose 5 pages into 31 components | 16h | Each page <300 lines |
| Add `useSettleNotification` hook | 1h | DRY in Settings |
| Add `React.lazy` code splitting | 2h | Bundle size reduction |
| Add `useReducer` to Orchestrate + KillLife | 4h | State management clarity |
| Memoize handlers with `useCallback` | 2h | Render performance |
| Replace JSON cloning with structuredClone | 0.5h | Performance |
| Add P0 test suite (hooks + utils) | 8h | Test coverage foundation |
| **Total** | **~35h** | |
