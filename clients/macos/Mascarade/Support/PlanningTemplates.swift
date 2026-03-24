//
//  PlanningTemplates.swift
//  Mascarade
//

import CoreData
import Foundation

struct VaultTemplate {
    let project: String
    let entryKind: EntryKind
    let status: EntryStatus
    let title: String
    let content: String
    let contentType: String
    let source: String
    let agentWritable: Bool

    var draft: EntryDraft {
        EntryDraft(
            project: project,
            entryKind: entryKind,
            status: status,
            title: title,
            content: content,
            contentType: contentType,
            source: source,
            agentWritable: agentWritable
        )
    }
}

struct TemplateUpsertService {
    func upsert(_ templates: [VaultTemplate], in context: NSManagedObjectContext, store: VaultStore) throws {
        for template in templates {
            let request = VaultEntry.fetchRequest()
            request.fetchLimit = 1
            request.predicate = NSPredicate(
                format: "title == %@ AND project == %@",
                template.title,
                template.project
            )

            let existingEntry = try context.fetch(request).first
            let draft = EntryDraft(
                id: existingEntry?.objectID,
                project: template.project,
                entryKind: template.entryKind,
                status: template.status,
                title: template.title,
                content: template.content,
                contentType: template.contentType,
                source: template.source,
                agentWritable: template.agentWritable
            )

            try store.saveEntry(from: draft, in: context)
        }
    }
}

enum PlanningTemplates {
    static let mascaradePack: [VaultTemplate] = [
        VaultTemplate(
            project: "Mascarade",
            entryKind: .plan,
            status: .active,
            title: "Mascarade Product Spine",
            content: """
            # Mascarade Product Spine

            - `Mascarade` est un cockpit Apple local-first pour piloter le gateway, les agents et les workflows.
            - La couche locale garde les plans, notes, docs et taches meme hors reseau.
            - La facade API reste un module separe pour observer le systeme vivant.
            """,
            contentType: "text/markdown",
            source: "seed",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .task,
            status: .active,
            title: "Porter le cockpit local de MCP-iCloud",
            content: """
            # Port de base

            - garder l'app SwiftUI existante
            - injecter un store Core Data local
            - exposer une surface cockpit avant la console reseau
            - garder visible la constellation des repos lies
            """,
            contentType: "text/markdown",
            source: "seed",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .task,
            status: .backlog,
            title: "Brancher Apple Intelligence et App Intents",
            content: """
            # Roadmap IA

            - reprendre les garde-fous de `MCP-iCloud`
            - limiter les actions aux operations bornees
            - garder la disponibilite locale comme prerequis
            """,
            contentType: "text/markdown",
            source: "seed",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Repo Mesh",
            entryKind: .doc,
            status: .active,
            title: "Mascarade linked repo constellation",
            content: """
            # Linked repo constellation

            - `/Users/electron/Documents/Lelectron_rare/Kill_LIFE` = control plane, contrats, spec-first, gouvernance et preuves.
            - `/Users/electron/Documents/Lelectron_rare/kill-life-studio` = extension VS Code orientee produit.
            - `/Users/electron/Documents/Lelectron_rare/kill-life-mesh` = extension VS Code orientee orchestration multi-repo.
            - `/Users/electron/Documents/Lelectron_rare/kill-life-operator` = extension VS Code orientee execution, runbooks et checks.
            - `/Users/electron/Documents/Lelectron_rare/Github_Repos/Perso/mascarade-main` = runtime API/core `3100 -> 8100`.
            - `/Users/electron/Documents/Lelectron_rare/Github_Repos/Perso/mascarade-cockpit` = console ops SvelteKit historique.
            - `/Users/electron/Documents/Lelectron_rare/electron-rare.github.io` = surface web publique Astro/React.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Kill_LIFE",
            entryKind: .doc,
            status: .active,
            title: "Kill LIFE tri-repo split",
            content: """
            # Kill LIFE tri-repo split

            - `Kill_LIFE` = control plane public, cockpit, contrats runtime/MCP/IA et navigation operateur.
            - `kill-life-studio` = surface produit/specs/roadmap.
            - `kill-life-mesh` = surface de synchronisation et handoffs multi-repo.
            - `kill-life-operator` = surface executionnelle et runbooks.
            - les trois extensions VS Code sont actuellement en `0.1.0-dev.1`.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade Runtime",
            entryKind: .doc,
            status: .active,
            title: "Mascarade runtime surfaces",
            content: """
            # Mascarade runtime surfaces

            - `mascarade-main` et `mascarade` documentent le meme coeur: API TypeScript sur `3100`, core Python sur `8100`.
            - le runtime orchestre plusieurs providers LLM, fallback, cache et agents specialises.
            - `mascarade-cockpit` reste la console ops SvelteKit SSR pour monitoring Docker, services et energie.
            - l'app Apple `Mascarade` doit agir comme client local-first de cet ensemble, pas comme duplicata serveur.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Operations",
            entryKind: .doc,
            status: .active,
            title: "Mascarade API Surface Map",
            content: """
            # Mascarade API Surface Map

            - `GET /health`
            - `GET /api/ops/summary`
            - `GET /api/agents`
            - `GET /api/killlife/workflows`
            """,
            contentType: "text/markdown",
            source: "ops",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Electron Rare",
            entryKind: .doc,
            status: .active,
            title: "Electron Rare web surface",
            content: """
            # Electron Rare web surface

            - `electron-rare.github.io` est un projet Astro 5 + React 19 + Storybook.
            - scripts canoniques: `npm run check`, `npm run build`, `npm run storybook:build`.
            - la doc README reste faible, donc l'app cockpit doit conserver un contexte operationnel minimal en local.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "ERP / Ops",
            entryKind: .doc,
            status: .active,
            title: "L'electronrare Ops bridge",
            content: """
            # L'electronrare Ops bridge

            ## Repo et build
            - repo prive `electron-rare/er-ops` sur GitHub: app React + Vite dediee aux operations.
            - build statique sur `root@192.168.0.119` sous `/root/er-ops-dist`.
            - le code pointe vers `https://api.lelectronrare.fr`; le pont mail conserve encore `Origin: https://ops.saillant.cc`.

            ## Surfaces publiees
            - `ops.saillant.cc` = surface ops interne, protegee par Authentik.
              - UI: header `ER / Ops`, 39 taches, bouton `Copilote IA`.
              - modules: Kanban, Calendrier, Agenda, Dashboard, Devis, Factures, Mail, Fichiers, Terminal, Pager, Code, Services, Factory.
            - `www.lelectronrare.fr/ops` = surface publique/editoriale.
              - modules: Kanban, Calendrier, Dashboard, Devis, Factures, Services, Factory, Digital Factory, Spec-First Pipeline.
            - les deux surfaces sont distinctes derriere le meme proxy Traefik, Authentik devant les deux.

            ## Infrastructure (photon)
            - publication: `zacus-cloudflared` → `zacus-traefik`.
            - route `ops.saillant.cc`: `/root/zacus-stack/config/traefik/dynamic/er-ops-react.yml` → `http://er-ops-react:4322` (sert `/root/er-ops-dist`).
            - route `www.lelectronrare.fr/ops`: `/root/zacus-stack/config/traefik/dynamic/electron-rare-site.yml` → `http://electron-rare-site:4321`.
            - tunnel Cloudflare couvre `*.saillant.cc` et `api.lelectronrare.fr`; `www.lelectronrare.fr` atteint Traefik par une autre publication amont.
            - acces direct sans session: `https://ops.saillant.cc/` redirige vers `https://auth.saillant.cc/...`.

            ## Contrats Kill_LIFE
            - couche ERP formalisee dans `specs/contracts/ops_kill_life_erp_registry.json`.
            - contrat de pont documente dans `docs/OPS_KILL_LIFE_ERP_BRIDGE_CONTRACT_2026-03-22.md`.
            - surface publique de reference pour les autres repos et `MCP-iCloud`: `https://www.lelectronrare.fr/ops`.

            ## Traitement Mascarade
            - traiter comme une surface ops reliee a l'ERP.
            - runtime dedie: `ops.saillant.cc`.
            - facade publique: `/ops`.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Operations",
            entryKind: .note,
            status: .blocked,
            title: "Questions ouvertes sur l'auth gateway",
            content: """
            # Questions ouvertes

            - faut-il imposer un bearer token sur tous les endpoints cockpit ?
            - quelle surface peut rester lisible depuis le LAN ?
            - comment differencier lecture, controle et actions sensibles ?
            """,
            contentType: "text/markdown",
            source: "ops",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Launch",
            entryKind: .task,
            status: .backlog,
            title: "Stabiliser la navigation multi-plateforme",
            content: """
            # UI cible

            - iPhone: navigation compacte et edition rapide
            - Mac: vue cockpit confortable pour tri et revue
            - visionOS: hierarchie lisible sans surcharge decorative
            """,
            contentType: "text/markdown",
            source: "launch",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Launch",
            entryKind: .task,
            status: .backlog,
            title: "iPhone: navigation compacte et edition rapide",
            content: """
            # iPhone: navigation compacte et edition rapide

            ## Conception UI
            - navigation bottom tab adaptee a la main unique.
            - edition rapide accessible en un tap depuis la liste (swipe action ou tap direct sur la row).
            - formulaire d'edition reduit au strict necessaire: titre, statut, contenu.
            - sheet ou inline edit selon le contexte.

            ## Developpement
            - verifier que `LocalCockpitView` et `VaultEntryEditor` sont confortables sur petit ecran.
            - ajuster les paddings et tailles de police pour iPhone SE / 15 Pro Max.
            - optimiser les performances de la `FetchRequest` avec un batch size adapte.
            - eviter les reflows inutiles sur le scroll de la liste d'entrees.

            ## Tests
            - tester sur iPhone SE (petit), iPhone 16 (standard), iPhone 16 Pro Max (grand).
            - verifier que l'edition rapide est intuitive: acces < 2 taps depuis la liste.
            - verifier que le clavier ne masque pas les champs critiques.
            """,
            contentType: "text/markdown",
            source: "launch",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Launch",
            entryKind: .task,
            status: .backlog,
            title: "Mac: vue cockpit confortable pour tri et revue",
            content: """
            # Mac: vue cockpit confortable pour tri et revue

            ## Conception UI
            - layout multi-colonnes pour tirer parti de l'espace disponible.
            - sidebar ou panneau gauche pour les filtres (statut, projet, archives).
            - colonne centrale pour la liste des entrees avec colonnes sortables.
            - panneau detail droit pour la preview/edition inline sans ouvrir de sheet.
            - toolbar Mac avec acces rapide aux actions frequentes.

            ## Developpement
            - utiliser `NavigationSplitView` pour sidebar + list + detail sur macOS.
            - adapter `LocalCockpitView` avec un `#if os(macOS)` ou via `ViewThatFits`.
            - implémenter un tri par colonne (titre, projet, statut, date) dans la liste.
            - tester `Table` SwiftUI pour la liste si le contenu le justifie.
            - optimiser les performances sur Mac Catalyst ou native macOS cible.

            ## Tests
            - tester sur MacBook Air (ecran 13), MacBook Pro (14, 16), Mac mini + ecran externe.
            - verifier que le tri et la revue sont fluides avec 100+ entrees.
            - s'assurer que les raccourcis clavier standards (Cmd+N, Cmd+F, Delete) fonctionnent.
            """,
            contentType: "text/markdown",
            source: "launch",
            agentWritable: true
        ),
        VaultTemplate(
            project: "ERP / Ops",
            entryKind: .task,
            status: .backlog,
            title: "Integrer Mascarade avec l'ERP / Ops Bridge",
            content: """
            # Integration Mascarade <-> ERP / Ops Bridge

            ## Analyse des besoins
            - identifier les donnees ERP pertinentes pour le cockpit Mascarade:
              taches (39 dans er-ops), devis, factures, services, statuts Factory.
            - identifier les points d'integration: API `api.lelectronrare.fr` ou surface directe `ops.saillant.cc`.
            - clarifier le modele d'auth: Authentik SSO, bearer token, ou acces LAN uniquement.
            - definir la frontiere entre lecture (affichage dans Mascarade) et ecriture (actions vers ERP).

            ## Developpement
            - ajouter un endpoint ERP dans `MascaradeAPI` ou creer un `ERPClient` separe.
            - modeliser les types ERP dans un fichier `ERPModels.swift` (taches, devis, services...).
            - ajouter un onglet ou une section dans le cockpit pour la surface ERP.
            - s'assurer que l'integration est offline-tolerante: pas de crash si l'ERP est inaccessible.
            - securiser: ne pas stocker de credentials ERP en clair, utiliser le Keychain.

            ## Tests
            - tester l'integration avec `ops.saillant.cc` (runtime dedie) et `www.lelectronrare.fr/ops` (facade publique).
            - verifier que les donnees sont correctement synchronisees et accessibles en lecture.
            - tester les cas d'erreur: ERP inaccessible, token expire, reponse malformee.
            - verifier que l'authentification Authentik est compatible avec le flow iOS/macOS.
            """,
            contentType: "text/markdown",
            source: "ops",
            agentWritable: true
        ),

        // MARK: - Specs techniques

        VaultTemplate(
            project: "Mascarade",
            entryKind: .doc,
            status: .active,
            title: "Architecture diagram Mascarade",
            content: """
            # Architecture Mascarade

            ```mermaid
            graph TD
                subgraph Apple App
                    A[MascaradeApp] --> B[ContentView]
                    B --> C[LocalCockpitView]
                    B --> D[DashboardView / Cabinet]
                    B --> E[AgentsView]
                    B --> F[WorkflowsView]
                    B --> G[SettingsView]
                    C --> H[VaultEntryEditor]
                    D --> I[CockpitViewModel]
                    E --> I
                    F --> I
                    G --> J[ConnectionSettings]
                    I --> J
                end

                subgraph Local Persistence
                    C --> K[VaultStore]
                    K --> L[(Core Data / SQLite)]
                    A --> M[PersistenceController]
                    M --> L
                    M --> N[PlanningTemplates seed]
                end

                subgraph Remote Runtime
                    I --> O[MascaradeAPI]
                    O -->|GET /health| P[mascarade-main :3100]
                    O -->|GET /api/ops/summary| P
                    O -->|GET /api/agents| P
                    O -->|GET /api/killlife/workflows| P
                    P --> Q[core Python :8100]
                    P --> R[Ollama LLM]
                    P --> S[Qdrant vector DB]
                end

                subgraph Security
                    J -->|baseURL| T[UserDefaults]
                    J -->|apiKey| U[Keychain]
                end
            ```
            """,
            contentType: "text/markdown",
            source: "spec",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .doc,
            status: .active,
            title: "Data flow diagram Mascarade",
            content: """
            # Data Flow Mascarade

            ```mermaid
            sequenceDiagram
                participant App as MascaradeApp
                participant VM as CockpitViewModel
                participant API as MascaradeAPI
                participant Runtime as mascarade-main :3100
                participant Store as VaultStore
                participant CD as Core Data

                App->>VM: refresh(using: settings)
                par concurrent calls
                    VM->>API: GET /health
                    API->>Runtime: HTTP GET /health
                    Runtime-->>API: HealthResponse
                    API-->>VM: health
                and
                    VM->>API: GET /api/ops/summary
                    API->>Runtime: HTTP GET /api/ops/summary
                    Runtime-->>API: OpsSummary
                    API-->>VM: summary
                and
                    VM->>API: GET /api/agents
                    API->>Runtime: HTTP GET /api/agents
                    Runtime-->>API: AgentsPayload
                    API-->>VM: agents[]
                and
                    VM->>API: GET /api/killlife/workflows
                    API->>Runtime: HTTP GET /api/killlife/workflows
                    Runtime-->>API: WorkflowsPayload
                    API-->>VM: workflows[]
                end
                VM->>VM: compute score, heat, bannerMessage

                Note over App,CD: Vault local (offline-first)
                App->>Store: saveEntry(draft)
                Store->>CD: NSManagedObjectContext.save()
                CD-->>Store: ok / error
                Store-->>App: void / VaultStoreError
            ```
            """,
            contentType: "text/markdown",
            source: "spec",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .doc,
            status: .active,
            title: "Feature map Mascarade v1",
            content: """
            # Feature Map Mascarade v1

            ```mermaid
            mindmap
              root((Mascarade))
                Cockpit local
                  CRUD entrees vault
                  Filtres statut/projet/search
                  Archives
                  Metriques locales
                  Seed templates
                Cabinet reseau
                  Score systeme
                  Heat index
                  Modes sabotage/parade/hasard
                  Orbites services animees
                  Spotlight agent/workflow
                  Shake to shuffle
                Agents
                  Liste avec search
                  Focus + capsule labels
                  Exhibit detail
                Lanes
                  Liste workflows
                  Metriques success/failed
                  Exhibit detail
                Rituel
                  URL base endpoint
                  API key Keychain
                  Presets localhost/VM
                  Refresh manuel
              roadmap
                Apple Intelligence
                  App Intents
                  FoundationModels on-device
                ERP Bridge
                  Lecture taches er-ops
                  Auth Authentik SSO
                Multi-plateforme
                  iPhone navigation compacte
                  Mac NavigationSplitView
                  visionOS
                Tests
                  VaultStore CRUD
                  MockURLSession
                  CockpitViewModel async
            ```
            """,
            contentType: "text/markdown",
            source: "spec",
            agentWritable: true
        ),

        // MARK: - Dette technique et corrections

        VaultTemplate(
            project: "Mascarade",
            entryKind: .doc,
            status: .active,
            title: "Analyse technique Mascarade 2026-03",
            content: """
            # Analyse technique Mascarade — mars 2026

            ## Score global: 4.4/10 (avant corrections)

            ## Corrections P1 realisees
            - `MascaradeAPI.swift:42` force unwrap `serverMessage!` → remplace par `.flatMap { $0.isEmpty ? nil : $0 } ?? fallback`. **DONE**
            - `ContentView.swift:513` force unwrap `firstIndex(of:)!` → remplace par `?? 0`. **DONE**
            - `ConnectionSettings.swift` API key en clair dans UserDefaults → migree vers Keychain (`kSecClassGenericPassword`, `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`). **DONE**

            ## Problemes P2 restants
            - `VaultStore`: pas de transactions atomiques → envelopper dans try/catch avec rollback.
            - `MascaradeAPI`: pas de retry logic → exponential backoff sur erreurs 5xx/timeout.
            - `CockpitViewModel`: pas de cache TTL → eviter refresh si <30s depuis le dernier.
            - `LocalCockpitView`: pas de confirmationDialog avant suppression.
            - `ContentView/LocalCockpitView`: @ObservedObject vs @StateObject a revoir.
            - `LocalCockpitView`: pas de debounce sur recherche.

            ## Problemes P3 restants
            - `ContentView.swift` = 2378 lignes → splitter en DashboardView.swift, AgentsView.swift, WorkflowsView.swift, SettingsView.swift.
            - `MascaradeAPI`: pas de support POST/PUT/DELETE.
            - `MascaradeModels`: String au lieu d'enums pour status/role/severity.
            - `VaultEntry.swift`: String.nonEmpty dupliquee avec VaultStore.
            - Pas de logging (os_log).
            - Pas d'accessibilite (VoiceOver).
            - Tests: couverture <10% → objectif 60%.

            ## Frameworks utilises vs importes
            | Framework | Utilise | Fichiers |
            |---|---|---|
            | SwiftUI | OUI | ContentView, LocalCockpitView, MascaradeApp |
            | Foundation | OUI | tous |
            | Combine | OUI | @Published, ObservableObject |
            | CoreData | OUI | Persistence, VaultStore, VaultEntry |
            | Security | OUI | ConnectionSettings (Keychain) |
            | Testing | OUI | MascaradeTests |

            ## Compatibilite Swift 6
            - async/await: 85% OK.
            - @MainActor isolation: 70% OK (ContentView, LocalCockpitView non isolees).
            - SwiftUI patterns: 65% OK (@ObservedObject a corriger).
            - Strict concurrency: 50% OK (activer `-strict-concurrency=complete`).
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .task,
            status: .backlog,
            title: "Splitter ContentView en fichiers separes",
            content: """
            # Refactor ContentView (2378 lignes)

            ## Objectif
            Extraire les vues internes en fichiers Swift independants pour ameliorer la maintenabilite.

            ## Plan
            - `DashboardView.swift` → tout le code Cabinet (DashboardView + composants internes).
            - `AgentsView.swift` → AgentsView.
            - `WorkflowsView.swift` → WorkflowsView + WorkflowDeckCard.
            - `SettingsView.swift` → SettingsView.
            - `ContentView.swift` garde: TabView, AppTab enum, CabinetMode enum, composants UI partages.

            ## Prerequis
            - Identifier les types/fonctions partages (deterministicAngle, statusText, latencyLabel).
            - Les extraire dans un fichier utilitaire `ViewHelpers.swift` si necessaire.

            ## Tests
            - Build et run apres chaque extraction.
            - Verifier que les previews fonctionnent dans chaque nouveau fichier.
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .task,
            status: .backlog,
            title: "Augmenter la couverture de tests (objectif 60%)",
            content: """
            # Tests — objectif 60% de couverture

            ## Etat actuel
            - 3 tests unitaires, 3 tests UI stubs.
            - Couverture: ~2%.

            ## Tests a ajouter

            ### VaultStore (30 tests prioritaires)
            - saveEntry avec titre valide
            - saveEntry rejette titre vide
            - saveEntry cree une entree avec updatedAt
            - saveEntry met a jour une entree existante
            - archive change isArchived = true
            - restore change isArchived = false
            - delete supprime l'entree du contexte
            - fetchEntry retourne nil si absent
            - fetchEntries avec filtre statut
            - fetchEntries avec recherche texte

            ### MascaradeAPI (15 tests)
            - creer un MockURLSession
            - get() reussit avec 200 + JSON valide
            - get() leve une erreur sur 401
            - get() leve une erreur sur 500 avec message serveur
            - get() leve une erreur sur timeout
            - get() decode le snake_case correctement

            ### CockpitViewModel (10 tests)
            - refresh() met a jour health apres succes
            - refresh() remplit bannerMessage apres echec partiel
            - refresh() ne crash pas si URL invalide
            - apiIsHealthy retourne true si status == "ok"

            ### ConnectionSettings (5 tests supplementaires)
            - update() ecrit l'URL dans UserDefaults
            - update() ecrit l'API key dans le Keychain
            - update() avec cle vide supprime l'entree Keychain
            - lecture Keychain apres ecriture retourne la meme valeur

            ## Structure recommandee
            ```
            MascaradeTests/
            ├── VaultStoreTests.swift
            ├── MascaradeAPITests.swift (avec MockURLSession)
            ├── CockpitViewModelTests.swift
            └── ConnectionSettingsTests.swift
            ```
            """,
            contentType: "text/markdown",
            source: "analysis",
            agentWritable: true
        ),
        VaultTemplate(
            project: "Mascarade",
            entryKind: .task,
            status: .backlog,
            title: "Evaluer integration FoundationModels on-device",
            content: """
            # Evaluation FoundationModels / Apple Intelligence

            ## Contexte
            Apple a introduit le framework `FoundationModels` (iOS 18.1+, macOS 15.1+) pour l'inference on-device via Apple Intelligence. Ce framework permet:
            - Generation de texte structuree avec macros Swift (@Generable).
            - Summarisation, classification, extraction.
            - Pas de dependance reseau pour les modeles Foundation.

            ## Cas d'usage potentiels pour Mascarade
            - Auto-completion du champ `content` lors de la creation d'une entree vault.
            - Suggestion de statut (backlog/active/blocked) basee sur le contenu.
            - Summarisation automatique d'une entree longue pour le `previewLine`.
            - Generation de missionLine dans le Cabinet a partir des donnees live.
            - Classification automatique des alertes par severite.

            ## Prerequis techniques
            - Deploiement minimum iOS 18.1 / macOS 15.1.
            - Entitlement `com.apple.developer.foundation-models.beta` en beta.
            - Appareil avec Apple Intelligence supporte (A17 Pro, M1+).

            ## Plan d'evaluation
            1. Verifier la disponibilite du framework dans le projet (import FoundationModels).
            2. Tester `LanguageModelSession` avec un prompt simple sur un champ vault.
            3. Evaluer la latence on-device vs appel Ollama distant.
            4. Documenter les limites (taille du contexte, modeles disponibles).
            5. Decider si FoundationModels remplace ou complement Ollama pour les taches legeres.

            ## App Intents integration
            - Exposer "Creer une entree vault" comme App Intent.
            - Exposer "Chercher dans le cockpit" comme App Intent.
            - Documenter dans `kill-life-operator` comme action disponible.
            """,
            contentType: "text/markdown",
            source: "roadmap",
            agentWritable: true
        ),
    ]
}
