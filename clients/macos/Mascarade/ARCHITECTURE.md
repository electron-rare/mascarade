# 🎨 Architecture Visuelle du Système

## 📱 Interface Utilisateur (SwiftUI)

```
┌────────────────────────────────────────────────────────────────────┐
│                         KanbanAI macOS App                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────────┐  ┌───────────────────────────────────────────┐  │
│  │   SIDEBAR    │  │           KANBAN BOARD                    │  │
│  │              │  │                                           │  │
│  │ Statistics   │  │  ┌────────┐ ┌────────┐ ┌────────┐       │  │
│  │ ┌──────────┐ │  │  │Backlog │ │  Todo  │ │Progress│  ...  │  │
│  │ │Tasks: 15 │ │  │  ├────────┤ ├────────┤ ├────────┤       │  │
│  │ │Done : 5  │ │  │  │ ┌────┐ │ │ ┌────┐ │ │ ┌────┐ │       │  │
│  │ │Rate : 33%│ │  │  │ │Task│ │ │ │Task│ │ │ │Task│ │       │  │
│  │ └──────────┘ │  │  │ │ 1  │ │ │ │ 2  │ │ │ │ 3  │ │       │  │
│  │              │  │  │ └────┘ │ │ └────┘ │ │ └────┘ │       │  │
│  │ Nodes P2P    │  │  │ ┌────┐ │ │        │ │        │       │  │
│  │ ┌──────────┐ │  │  │ │Task│ │ │        │ │        │       │  │
│  │ │🟢 root   │ │  │  │ │ 4  │ │ │        │ │        │       │  │
│  │ │🟢 clems  │ │  │  │ └────┘ │ │        │ │        │       │  │
│  │ │🟢 kxkm   │ │  │  └────────┘ └────────┘ └────────┘       │  │
│  │ │🔴 cils   │ │  │                                           │  │
│  │ └──────────┘ │  └───────────────────────────────────────────┘  │
│  │              │                                                  │
│  │ Actions      │                                                  │
│  │ • Add Task   │                                                  │
│  │ • Refresh    │                                                  │
│  └──────────────┘                                                  │
└────────────────────────────────────────────────────────────────────┘
```

## 🏗️ Architecture en Couches

```
┌─────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                     │
│                         (SwiftUI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ KanbanBoard │  │ NodeManager │  │  AddTask    │        │
│  │    View     │  │    View     │  │    View     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└──────────────────────────┬──────────────────────────────────┘
                           │ @Published / @StateObject
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     VIEW MODEL LAYER                        │
│                    (@MainActor)                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │              KanbanBoard                          │     │
│  │  • tasks: [KanbanTask]                            │     │
│  │  • nodes: [P2PNode]                               │     │
│  │  • addTask(), updateTask(), deleteTask()          │     │
│  │  • processTaskWithAI()                            │     │
│  │  • refreshNodes()                                 │     │
│  └───────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────┘
                           │ async/await
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                           │
│                       (Actors)                              │
│  ┌────────────────────┐         ┌────────────────────┐     │
│  │ P2PConnection      │         │  AITask            │     │
│  │    Manager         │ ◄─────► │   Executor         │     │
│  │                    │         │                    │     │
│  │ • connect()        │         │ • executeTask()    │     │
│  │ • disconnect()     │         │ • executeParallel()│     │
│  │ • executeCommand() │         │ • monitorProgress()│     │
│  │ • pingAllNodes()   │         │                    │     │
│  │ • findBestNode()   │         │                    │     │
│  └────────────────────┘         └────────────────────┘     │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSH / Process
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     NETWORK LAYER                           │
│                     (SSH Protocol)                          │
│  ┌───────────────────────────────────────────────────┐     │
│  │  /usr/bin/ssh -o StrictHostKeyChecking=no ...     │     │
│  │  • Process                                         │     │
│  │  • Pipe (stdin/stdout/stderr)                      │     │
│  │  • Authentication (public key)                     │     │
│  └───────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────┘
                           │ TCP/IP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  DISTRIBUTED P2P LAYER                      │
│                    (Remote Nodes)                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ root@.119    │  │ clems@.120   │  │ kxkm@kxkm-ai │     │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤     │
│  │ mascarade_   │  │ mascarade_   │  │ mascarade_   │     │
│  │    ai.py     │  │    ai.py     │  │    ai.py     │     │
│  │              │  │              │  │              │     │
│  │ 📊 Data      │  │ 📝 Text      │  │ 🧠 ML        │     │
│  │ 🤖 Training  │  │ 🖼️  Image    │  │ 🔮 Inference │     │
│  │ 🔮 Inference │  │ 🔮 Inference │  │ 📊 Data      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Flux de Données Complet

### Création et Traitement d'une Tâche

```
┌──────────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                              │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Tap "Add Task"
                            ▼
                  ┌───────────────────┐
                  │   AddTaskView     │
                  │  • Title          │
                  │  • Description    │
                  │  • Priority       │
                  └─────────┬─────────┘
                            │ onSave()
                            ▼
                  ┌───────────────────┐
                  │  KanbanBoard      │
                  │  .addTask(task)   │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │  tasks.append()   │
                  │  saveTasks()      │
                  │  @Published       │
                  └─────────┬─────────┘
                            │ UI Update
                            ▼
                  ┌───────────────────┐
                  │ KanbanBoardView   │
                  │ (Refreshed)       │
                  └─────────┬─────────┘
                            │ User taps "Process with AI"
                            ▼
                  ┌───────────────────┐
                  │ KanbanBoard       │
                  │ .processTaskWith  │
                  │    AI(task)       │
                  └─────────┬─────────┘
                            │ async
                            ▼
                  ┌───────────────────┐
                  │ AITaskExecutor    │
                  │ .executeTask()    │
                  └─────────┬─────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    ┌─────────────────┐        ┌─────────────────┐
    │ P2PConnection   │        │ Build Mascarade │
    │ Manager         │        │ Command         │
    │ .findBestNode() │        │                 │
    └────────┬────────┘        └────────┬────────┘
             │                          │
             └──────────┬───────────────┘
                        ▼
              ┌─────────────────┐
              │ SSH Connection  │
              │ to best node    │
              └────────┬────────┘
                       │ python3 mascarade_ai.py process {...}
                       ▼
         ┌────────────────────────────┐
         │  Remote Node (e.g., root)  │
         │  mascarade_ai.py           │
         │  • Parse JSON              │
         │  • Route to handler        │
         │  • Execute AI processing   │
         │  • Return JSON result      │
         └──────────┬─────────────────┘
                    │ JSON Response
                    ▼
         ┌────────────────────────────┐
         │  AITaskExecutor            │
         │  • Receive result          │
         │  • Parse response          │
         └──────────┬─────────────────┘
                    │
                    ▼
         ┌────────────────────────────┐
         │  KanbanBoard               │
         │  • Update task status      │
         │  • Set AI result           │
         │  • Status → Review         │
         └──────────┬─────────────────┘
                    │ @Published
                    ▼
         ┌────────────────────────────┐
         │  KanbanBoardView           │
         │  • UI refreshed            │
         │  • Task shows result       │
         │  • Progress bar updated    │
         └────────────────────────────┘
```

## ⚡ Traitement Parallèle

```
┌─────────────────────────────────────────────────────────────┐
│           USER: "Process all TODO tasks"                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  KanbanBoard         │
              │  .processTasks       │
              │   Concurrently()     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  AITaskExecutor      │
              │  withTaskGroup {     │
              │    addTask(task1)    │
              │    addTask(task2)    │
              │    addTask(task3)    │
              │  }                   │
              └──────────┬───────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  ┌─────────┐      ┌─────────┐      ┌─────────┐
  │ Task 1  │      │ Task 2  │      │ Task 3  │
  │    ↓    │      │    ↓    │      │    ↓    │
  │ root@   │      │ clems@  │      │ kxkm@   │
  │ .119    │      │ .120    │      │ kxkm-ai │
  └────┬────┘      └────┬────┘      └────┬────┘
       │                │                │
       │   Parallel     │   Execution    │
       │                │                │
       ▼                ▼                ▼
  ┌─────────┐      ┌─────────┐      ┌─────────┐
  │Result 1 │      │Result 2 │      │Result 3 │
  └────┬────┘      └────┬────┘      └────┬────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │  Collect Results     │
              │  Update UI           │
              └──────────────────────┘
```

## 🎯 Sélection du Meilleur Nœud (Load Balancing)

```
┌──────────────────────────────────────────────────────────────┐
│               Task requires: "textProcessing"                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ P2PConnectionManager │
              │ .findBestNode(       │
              │   capability)        │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
    ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
    │ root   │      │ clems  │      │ kxkm   │      │ cils   │
    ├────────┤      ├────────┤      ├────────┤      ├────────┤
    │Status: │      │Status: │      │Status: │      │Status: │
    │ ONLINE │      │ ONLINE │      │ ONLINE │      │OFFLINE │
    │        │      │        │      │        │      │   ❌   │
    │Load:   │      │Load:   │      │Load:   │      └────────┘
    │ 85%  ❌│      │ 45%  ✓ │      │ 90%  ❌│
    │        │      │        │      │        │
    │Has Cap:│      │Has Cap:│      │Has Cap:│
    │ ❌     │      │ ✓      │      │ ❌     │
    └────────┘      └────────┘      └────────┘
                         │
                         │ SELECTED ✅
                         │ (Online, Low Load, Has Capability)
                         ▼
                    ┌────────┐
                    │ clems@ │
                    │ .120   │
                    └────────┘
```

## 🔐 Flux de Sécurité SSH

```
┌──────────────────────────────────────────────────────────────┐
│                     macOS Application                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Read SSH Config     │
              │  ~/.ssh/id_ed25519   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Create SSH Process  │
              │  with Public Key     │
              │  Authentication      │
              └──────────┬───────────┘
                         │ Encrypted Connection
                         ▼
              ┌──────────────────────┐
              │  SSH Handshake       │
              │  • Key Exchange      │
              │  • Authentication    │
              │  • Session Setup     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Secure Channel      │
              │  Established         │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Execute Command     │
              │  python3 ...         │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Receive Output      │
              │  (Encrypted)         │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Close Connection    │
              └──────────────────────┘
```

## 📊 Monitoring et Statistiques

```
┌──────────────────────────────────────────────────────────────┐
│                    REAL-TIME DASHBOARD                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 BOARD STATISTICS                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Total Tasks: 15                                       │ │
│  │  ├─ Backlog     : ███░░░░░░░ 3                         │ │
│  │  ├─ TODO        : ████░░░░░░ 4                         │ │
│  │  ├─ In Progress : ██░░░░░░░░ 2                         │ │
│  │  ├─ AI Process  : ███░░░░░░░ 3                         │ │
│  │  ├─ Review      : █░░░░░░░░░ 1                         │ │
│  │  └─ Done        : ██░░░░░░░░ 2                         │ │
│  │                                                         │ │
│  │  Completion Rate: 13% ████░░░░░░░░░░░░░░░░░░░░░░       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  🌐 NODES STATUS                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  root@192.168.0.119   🟢 Online  ████████░░ 80%        │ │
│  │  clems@192.168.0.120  🟢 Online  █████░░░░░ 50%        │ │
│  │  kxkm@kxkm-ai         🟢 Online  █████████░ 90%        │ │
│  │  user@cils            🔴 Offline ░░░░░░░░░░  0%        │ │
│  │                                                         │ │
│  │  Node Availability: 75% ███████████████░░░░░           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ⚡ ACTIVE AI PROCESSING                                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Task #3 → root@.119    [████████░░] 80%               │ │
│  │  Task #7 → clems@.120   [████░░░░░░] 40%               │ │
│  │  Task #9 → kxkm-ai      [██████████] 100% ✅           │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## 🗂️ Data Flow dans le Système

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA FLOW                            │
└─────────────────────────────────────────────────────────────┘

SwiftUI State (@Published)
    ↓
ObservableObject (KanbanBoard)
    ↓
Actor (AITaskExecutor) ─────→ Actor (P2PConnectionManager)
    ↓                                  ↓
Task<Result, Error>                SSH Process
    ↓                                  ↓
await                              Pipe (stdout)
    ↓                                  ↓
JSON Response ←────────────────────────┘
    ↓
Codable Parsing
    ↓
Model Update (KanbanTask)
    ↓
@Published Notification
    ↓
SwiftUI Re-render
```

---

**Cette architecture garantit :**
- ✅ Thread-safety (Actors)
- ✅ Réactivité UI (@Published)
- ✅ Distribution P2P (SSH)
- ✅ Scalabilité (Async/Await)
- ✅ Sécurité (SSH Keys)
- ✅ Performance (Parallel Tasks)
