# 💡 Exemples d'Utilisation Pratiques

Ce document présente des cas d'usage concrets du système Kanban IA P2P.

---

## 🎯 Cas d'Usage 1 : Analyse de Sentiment

### Scénario
Vous avez collecté des feedbacks clients et vous souhaitez analyser leur sentiment.

### Étapes dans l'Application

1. **Créer une tâche** (⌘N)
   - Titre : "Analyser le sentiment des feedbacks clients"
   - Description : "Produit excellent, très satisfait du service !"
   - Priorité : Moyenne
   - Tags : ["NLP", "clients", "feedback"]

2. **Traiter avec l'IA**
   - Menu ⋯ → "Traiter avec IA"
   - Sélectionner : "Traitement de texte"
   - Le système choisit automatiquement le meilleur nœud (ex: clems@192.168.0.120)

3. **Résultat**
   ```json
   {
     "sentiment": "positive",
     "confidence": 0.95,
     "keywords": ["excellent", "satisfait", "service"],
     "word_count": 8,
     "emotion": "joy"
   }
   ```

### Commande SSH équivalente
```bash
ssh clems@192.168.0.120 "python3 /opt/mascarade/mascarade_ai.py process \
  '{\"id\":\"task1\",\"title\":\"Analyser sentiment\",\"description\":\"Produit excellent, très satisfait du service !\",\"capability\":\"textProcessing\"}'"
```

---

## 🎯 Cas d'Usage 2 : Traitement Parallèle de Rapports

### Scénario
Vous devez traiter 10 rapports simultanément.

### Étapes dans l'Application

1. **Créer 10 tâches** rapidement
   - Utilisez un script ou créez-les manuellement
   - Toutes en statut "TODO"
   - Tags : ["rapports", "analyse"]

2. **Traitement en lot**
   - Menu Actions → "Traiter toutes les tâches TODO"
   - Le système distribue automatiquement :
     - 3 tâches → root@192.168.0.119
     - 3 tâches → clems@192.168.0.120
     - 4 tâches → kxkm@kxkm-ai

3. **Monitoring en temps réel**
   - Voir la progression dans la sidebar
   - Chaque tâche affiche sa barre de progression
   - Notifications à la fin

### Code Swift équivalent
```swift
let todoTasks = board.tasks(for: .todo)
await board.processTasksConcurrently(
    todoTasks,
    capability: .dataProcessing
)
```

---

## 🎯 Cas d'Usage 3 : Pipeline de Traitement ML

### Scénario
Pipeline ML complet : data → training → inference

### Workflow

**Tâche 1 : Préparation des Données**
- Titre : "Nettoyer et préparer le dataset"
- Capacité : Data Processing
- Nœud : root@192.168.0.119
- Résultat : Dataset nettoyé

**Tâche 2 : Entraînement du Modèle** (dépend de Tâche 1)
- Titre : "Entraîner le modèle de classification"
- Capacité : Model Training
- Nœud : kxkm@kxkm-ai
- Résultat : Modèle entraîné

**Tâche 3 : Inférence** (dépend de Tâche 2)
- Titre : "Prédictions sur nouvelles données"
- Capacité : Inference
- Nœud : root@192.168.0.119
- Résultat : Prédictions

### Dans l'interface
```
BACKLOG → TODO → IN_PROGRESS → AI_PROCESSING → REVIEW → DONE
   T1       T2         T3             T1          T2      T3
                                      (root)    (kxkm)  (root)
```

---

## 🎯 Cas d'Usage 4 : Load Balancing Intelligent

### Scénario
Vous avez 5 tâches à traiter, mais certains nœuds sont occupés.

### État Initial
```
Nœuds :
  root@.119  : 85% charge  (occupé)
  clems@.120 : 45% charge  ✅
  kxkm-ai    : 90% charge  (occupé)
  cils       : OFFLINE
```

### Distribution Automatique
Le système choisit intelligemment :
- Toutes les tâches → clems@192.168.0.120 (seul nœud disponible < 80%)
- File d'attente pour les autres tâches
- Retry automatique quand les nœuds se libèrent

### Code de Load Balancing
```swift
// Dans P2PConnectionManager
func findBestNode(for capability: AICapability) -> P2PNode? {
    let availableNodes = nodes.values.filter { node in
        node.capabilities.contains(capability) &&
        node.status == .online &&
        node.currentLoad < 0.8  // Moins de 80%
    }
    
    // Trier par charge (ascendant)
    return availableNodes.sorted { 
        $0.currentLoad < $1.currentLoad 
    }.first
}
```

---

## 🎯 Cas d'Usage 5 : Monitoring et Alertes

### Scénario
Surveiller l'état du système en temps réel.

### Dashboard Temps Réel

**Statistiques Affichées**
```
📊 BOARD STATISTICS
─────────────────────
Total Tasks    : 25
Backlog        : 5   (20%)
TODO           : 8   (32%)
In Progress    : 4   (16%)
AI Processing  : 3   (12%)
Review         : 3   (12%)
Done           : 2   (8%)

Completion     : 8%  ████░░░░░░░░░░░░░░░░
```

**État des Nœuds**
```
🌐 NODES STATUS
─────────────────────
root@.119      : 🟢 Online  (75% charge)
clems@.120     : 🟢 Online  (45% charge)
kxkm-ai        : 🟢 Online  (85% charge)
cils           : 🔴 Offline

Availability   : 75% ███████████████░░░░░
```

### Vérification Manuelle
```bash
# Via Makefile
make status

# Via SSH directement
make ssh-root
python3 /opt/mascarade/mascarade_ai.py status
```

---

## 🎯 Cas d'Usage 6 : Gestion d'Erreurs et Retry

### Scénario
Une tâche échoue sur un nœud, le système la réessaie automatiquement.

### Flow d'Exécution

**Tentative 1 : root@192.168.0.119**
```
Task #5 → root@.119
Status: AI Processing
Progress: 45%
ERROR: Connection timeout
```

**Retry Automatique : clems@192.168.0.120**
```
Task #5 → clems@.120 (retry)
Status: AI Processing
Progress: 100%
Result: Success ✅
```

### Code de Retry
```swift
func executeTask(
    _ task: KanbanTask,
    capability: P2PNode.AICapability,
    retries: Int = 3
) async throws -> String {
    var lastError: Error?
    
    for attempt in 1...retries {
        do {
            return try await executeTaskOnce(task, capability: capability)
        } catch {
            lastError = error
            if attempt < retries {
                try await Task.sleep(for: .seconds(5))
            }
        }
    }
    
    throw lastError ?? ExecutionError.noAvailableNode
}
```

---

## 🎯 Cas d'Usage 7 : Personnalisation des Handlers IA

### Scénario
Ajouter votre propre traitement IA personnalisé.

### Modifier mascarade_ai.py

**Ajouter une nouvelle capacité**
```python
# Dans mascarade_ai.py

def _handle_custom_analysis(self, task_data: Dict[str, Any]) -> str:
    """Votre traitement personnalisé"""
    import requests  # ou toute autre bibliothèque
    
    # Votre logique métier
    data = task_data.get('description', '')
    
    # Appel API externe (exemple)
    response = requests.post('https://your-api.com/analyze', {
        'text': data
    })
    
    result = {
        'analysis': response.json(),
        'custom_metric': 42,
        'timestamp': datetime.now().isoformat()
    }
    
    return json.dumps(result, indent=2)
```

**Ajouter au router**
```python
handlers = {
    'textProcessing': self._handle_text_processing,
    'customAnalysis': self._handle_custom_analysis,  # ← Nouveau
    # ... autres handlers
}
```

**Utiliser dans l'app Swift**
```swift
// Ajouter la capacité dans P2PNode.swift
enum AICapability: String, Codable, CaseIterable {
    case textProcessing = "Traitement de texte"
    case customAnalysis = "Analyse personnalisée"  // ← Nouveau
    // ...
}
```

---

## 🎯 Cas d'Usage 8 : Intégration avec API Externe

### Scénario
Utiliser une API externe (ex: OpenAI GPT) dans le traitement.

### Configuration

**Sur le nœud distant**
```bash
ssh root@192.168.0.119
pip3 install openai
export OPENAI_API_KEY="your-key-here"
```

**Modifier le handler**
```python
def _handle_inference(self, task_data: Dict[str, Any]) -> str:
    """Inférence avec GPT"""
    import openai
    
    prompt = task_data.get('description', '')
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    
    result = {
        'gpt_response': response.choices[0].message.content,
        'model': 'gpt-4',
        'tokens_used': response.usage.total_tokens
    }
    
    return json.dumps(result, indent=2)
```

**Utilisation**
- Créer une tâche avec description = votre prompt
- Sélectionner "Inference" comme capacité
- Le système appelle GPT et retourne la réponse

---

## 🎯 Cas d'Usage 9 : Export et Reporting

### Scénario
Exporter toutes les tâches terminées pour un rapport.

### Code Swift pour Export JSON
```swift
extension KanbanBoard {
    func exportCompletedTasks() -> String? {
        let completedTasks = tasks.filter { $0.status == .done }
        
        let encoder = JSONEncoder()
        encoder.outputFormatting = .prettyPrinted
        encoder.dateEncodingStrategy = .iso8601
        
        guard let data = try? encoder.encode(completedTasks),
              let json = String(data: data, encoding: .utf8) else {
            return nil
        }
        
        return json
    }
    
    func saveExport(to url: URL) {
        guard let json = exportCompletedTasks() else { return }
        try? json.write(to: url, atomically: true, encoding: .utf8)
    }
}
```

### Utilisation
```swift
// Dans la vue
Button("Exporter les tâches terminées") {
    let panel = NSSavePanel()
    panel.nameFieldStringValue = "tasks-export.json"
    panel.allowedContentTypes = [.json]
    
    if panel.runModal() == .OK, let url = panel.url {
        board.saveExport(to: url)
    }
}
```

---

## 🎯 Cas d'Usage 10 : Automatisation avec Scripts

### Scénario
Automatiser la création de tâches depuis un fichier CSV.

### Script Python
```python
#!/usr/bin/env python3
import csv
import json
import subprocess

def create_tasks_from_csv(csv_file):
    """Créer des tâches depuis un CSV"""
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            task = {
                "title": row['title'],
                "description": row['description'],
                "priority": row.get('priority', 'medium'),
                "tags": row.get('tags', '').split(',')
            }
            
            # Envoyer à l'app via AppleScript ou file watcher
            print(f"Creating task: {task['title']}")
            # Implementation dépend de votre setup

if __name__ == '__main__':
    create_tasks_from_csv('tasks.csv')
```

### CSV Exemple
```csv
title,description,priority,tags
Analyse données Q1,Traiter les données du premier trimestre,high,data,analytics
Review code PR #123,Vérifier la pull request,medium,code,review
Deploy v2.0,Déployer la nouvelle version,urgent,deployment,production
```

---

## 🎯 Cas d'Usage 11 : Health Monitoring Avancé

### Scénario
Surveiller la santé des nœuds avec alertes.

### Script de Monitoring
```bash
#!/bin/bash
# health_monitor.sh

while true; do
    make test-remote-all > /tmp/health_check.log
    
    if grep -q "❌" /tmp/health_check.log; then
        # Envoyer une alerte (email, Slack, etc.)
        echo "⚠️ ALERT: Some nodes are down!" | \
            mail -s "P2P Health Alert" admin@example.com
    fi
    
    sleep 300  # Vérifier toutes les 5 minutes
done
```

### Intégration macOS
```swift
// Dans KanbanBoard
func startHealthMonitoring() {
    Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { _ in
        Task {
            await self.checkNodesHealth()
        }
    }
}

private func checkNodesHealth() async {
    await connectionManager.pingAllNodes()
    let offlineNodes = nodes.filter { $0.status == .offline }
    
    if !offlineNodes.isEmpty {
        // Afficher une notification macOS
        let notification = UNMutableNotificationContent()
        notification.title = "Nœuds P2P Hors Ligne"
        notification.body = "\(offlineNodes.count) nœud(s) ne répond(ent) pas"
        notification.sound = .default
        
        // Envoyer la notification
    }
}
```

---

## 🎯 Cas d'Usage 12 : Workflow Avancé Multi-Étapes

### Scénario
Pipeline complexe avec dépendances entre tâches.

### Définition du Workflow
```swift
struct Workflow {
    let id: UUID
    let name: String
    var steps: [WorkflowStep]
}

struct WorkflowStep {
    let id: UUID
    let task: KanbanTask
    let dependsOn: [UUID]  // IDs des étapes précédentes
    var status: StepStatus
    
    enum StepStatus {
        case waiting
        case ready
        case running
        case completed
        case failed
    }
}
```

### Exécution
```swift
class WorkflowExecutor {
    func execute(_ workflow: Workflow) async {
        var completed: Set<UUID> = []
        
        while completed.count < workflow.steps.count {
            for step in workflow.steps {
                // Vérifier si toutes les dépendances sont complétées
                let canRun = step.dependsOn.allSatisfy { 
                    completed.contains($0) 
                }
                
                if canRun && step.status == .ready {
                    // Exécuter l'étape
                    await executeStep(step)
                    completed.insert(step.id)
                }
            }
            
            try? await Task.sleep(for: .seconds(1))
        }
    }
}
```

---

## 💡 Conseils et Best Practices

### ✅ Optimisation des Performances
1. **Grouper les tâches similaires** pour utiliser le même nœud
2. **Utiliser le traitement parallèle** pour > 3 tâches
3. **Surveiller la charge** avant d'envoyer de nouvelles tâches

### ✅ Gestion des Erreurs
1. **Toujours implémenter le retry logic**
2. **Logger toutes les erreurs** pour debugging
3. **Avoir un fallback** si tous les nœuds sont down

### ✅ Sécurité
1. **Utiliser uniquement des clés SSH**
2. **Valider toutes les entrées** avant envoi
3. **Ne jamais logger de secrets**

### ✅ Maintenance
1. **Vérifier les nœuds régulièrement** (`make status`)
2. **Consulter les logs** (`make logs-all`)
3. **Mettre à jour les dépendances Python** périodiquement

---

## 🚀 Aller Plus Loin

### Ressources Additionnelles
- **Documentation Swift Concurrency** : https://docs.swift.org/swift-book/LanguageGuide/Concurrency.html
- **SwiftUI Tutorials** : https://developer.apple.com/tutorials/swiftui
- **Python ML Libraries** : numpy, pandas, scikit-learn, transformers

### Exemples Avancés
Consultez :
- `Scripts/demo_mascarade.py` - Démos interactives
- `Tests/KanbanAITests.swift` - Tests comme exemples
- `ARCHITECTURE.md` - Diagrammes détaillés

---

**Avec ces exemples, vous êtes prêt à exploiter tout le potentiel du système ! 🎉**
