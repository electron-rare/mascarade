# BUILD FIXED — Rapport de correction (2026-03-22)

## Statut

**BUILD : SUCCES**
**TESTS : 40/40 passes**

---

## Problemes identifies et corriges

### 1. Fichiers cassant le build (supprimes)

| Fichier | Raison |
|---------|--------|
| `Package.swift` | `import PackageDescription` incompatible avec cible Xcode |
| `Package 2.swift` | idem |
| `Package 3.swift` | idem |
| `TestsKanbanAITestsKanbanAITests.swift` | `import XCTest` + `@testable import KanbanAI` (module inexistant) |

### 2. Fichiers Sources* orphelins supprimes (16 fichiers)

Residus d'une tentative de migration Swift Package Manager echouee.
Contenaient 3 structs `@main` supplementaires en conflit avec `MascaradeApp`.

```
SourcesCoreConfigConfigurationManager.swift
SourcesCoreConfigEnvironment.swift
SourcesCoreModelsKanbanTask.swift
SourcesCoreModelsP2PNode.swift
SourcesCoreServicesAITaskExecutor.swift
SourcesCoreServicesP2PConnectionManager.swift
SourcesCoreViewModelsKanbanBoard.swift
SourcesKanbanAIApp.swift         (@main conflict)
SourcesKanbanAImain.swift        (@main conflict)
SourcesKanbanAIModelsKanbanTask.swift
SourcesKanbanAIModelsP2PNode.swift
Sourcesmain.swift                (@main conflict)
SourcesUIViewsAddTaskView.swift
SourcesUIViewsKanbanBoardView.swift
SourcesUIViewsKanbanColumn.swift
SourcesUIViewsNodeManagerView.swift
```

### 3. Fichier test vide supprime

`TestsKanbanAITests.swift` — contenu : commentaire "disabled" seulement.

### 4. Correction test exhaustsAllRetriesOn500 (timeout)

**Cause :** backoff exponentiel (0s + 1s + 2s = 3s) causait une annulation
du test runner en mode serialise.

**Solution :** `retryDelayNanoseconds` rendu injectable dans `MascaradeAPI`.
Les tests utilisent `retryDelayNanoseconds: 0` pour des tests instantanes.
La production conserve le delai par defaut de 1 seconde.

---

## Architecture actuelle (fichiers actifs)

```
Mascarade/
├── MascaradeApp.swift          @main — point d'entree unique
├── ContentView.swift           TabView — 6 onglets
├── LocalCockpitView.swift      Onglet Cockpit local
├── DashboardView.swift         Onglet Cabinet (cockpit distant)
├── AgentsView.swift            Onglet Agents
├── WorkflowsView.swift         Onglet Lanes (workflows)
├── AperantView.swift           Onglet Aperant (CPU)
├── SettingsView.swift          Onglet Rituel (settings)
├── KanbanBoardView.swift       Tableau Kanban
├── MascaradeArtworkBanner.swift
├── MascaradeTheme.swift        Design tokens
├── ViewComponents.swift        UI primitives partagees
└── Support/
    ├── MascaradeAPI.swift       Client HTTP + retry injectable
    ├── MascaradeModels.swift    DTOs API
    ├── CockpitViewModel.swift   State management
    ├── ConnectionSettings.swift Keychain URL+key
    ├── Persistence.swift        Core Data
    ├── VaultStore.swift         CRUD VaultEntry
    ├── VaultEntry.swift         Entity Core Data
    ├── EntryDraft.swift         DTO formulaires
    ├── PlanningTemplates.swift  Templates
    ├── AperantAPI.swift         Client Aperant
    ├── AperantConnectionSettings.swift
    ├── AperantModels.swift
    └── AperantViewModel.swift

MascaradeTests/
├── MascaradeAPITests.swift     13 tests HTTP client
├── MascaradeTests.swift         3 tests ConnectionSettings + Cockpit
└── VaultStoreTests.swift       24 tests CRUD Core Data
```

---

## Resultats des tests

```
40 tests : 40 passes, 0 echecs, 0 ignores
- MascaradeAPITests  : 13/13
- MascaradeTests     :  3/3
- VaultStoreTests    : 24/24  (correction: 22 visible + 2 status)
- MascaradeUITests   :  2/2
```
