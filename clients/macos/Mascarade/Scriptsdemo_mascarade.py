#!/usr/bin/env python3
"""
Exemples d'utilisation du système IA Mascarade
Démonstrations pratiques des différentes capacités
"""

import json
import subprocess
import sys

def execute_ssh_command(host, command):
    """Exécute une commande SSH sur un hôte distant"""
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", host, command]
    result = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def demo_text_processing():
    """Démonstration du traitement de texte"""
    print("=" * 60)
    print("📝 DÉMONSTRATION : TRAITEMENT DE TEXTE")
    print("=" * 60)
    
    task = {
        "id": "demo-001",
        "title": "Analyser le sentiment de ce texte",
        "description": "Swift est un langage de programmation moderne et puissant pour développer des applications Apple.",
        "capability": "textProcessing"
    }
    
    print(f"\n📤 Envoi de la tâche : {task['title']}")
    print(f"📄 Texte : {task['description']}")
    
    command = f"python3 /opt/mascarade/mascarade_ai.py process '{json.dumps(task)}'"
    
    # Tester sur le nœud clems (bon pour le texte)
    print("\n🔄 Traitement sur clems@192.168.0.120...")
    stdout, stderr, code = execute_ssh_command("clems@192.168.0.120", command)
    
    if code == 0:
        result = json.loads(stdout)
        print("\n✅ Résultat :")
        print(json.dumps(result, indent=2))
    else:
        print(f"❌ Erreur : {stderr}")

def demo_data_processing():
    """Démonstration du traitement de données"""
    print("\n" + "=" * 60)
    print("📊 DÉMONSTRATION : TRAITEMENT DE DONNÉES")
    print("=" * 60)
    
    task = {
        "id": "demo-002",
        "title": "Traiter un dataset de performance",
        "description": "Analyser les métriques de performance des nœuds P2P",
        "capability": "dataProcessing",
        "data": {
            "metrics": [
                {"node": "root", "cpu": 45, "memory": 60},
                {"node": "clems", "cpu": 30, "memory": 55},
                {"node": "kxkm", "cpu": 80, "memory": 75},
            ]
        }
    }
    
    print(f"\n📤 Envoi de la tâche : {task['title']}")
    print(f"📊 Données : {len(task.get('data', {}).get('metrics', []))} entrées")
    
    command = f"python3 /opt/mascarade/mascarade_ai.py process '{json.dumps(task)}'"
    
    # Tester sur le nœud root (bon pour data processing)
    print("\n🔄 Traitement sur root@192.168.0.119...")
    stdout, stderr, code = execute_ssh_command("root@192.168.0.119", command)
    
    if code == 0:
        result = json.loads(stdout)
        print("\n✅ Résultat :")
        print(json.dumps(result, indent=2))
    else:
        print(f"❌ Erreur : {stderr}")

def demo_inference():
    """Démonstration d'inférence IA"""
    print("\n" + "=" * 60)
    print("🧠 DÉMONSTRATION : INFÉRENCE IA")
    print("=" * 60)
    
    task = {
        "id": "demo-003",
        "title": "Classifier cette tâche Kanban",
        "description": "Implémenter l'authentification OAuth2 dans l'application mobile",
        "capability": "inference",
        "context": {
            "tags": ["backend", "sécurité", "mobile"],
            "priority": "high"
        }
    }
    
    print(f"\n📤 Envoi de la tâche : {task['title']}")
    print(f"🏷️  Tags : {', '.join(task['context']['tags'])}")
    
    command = f"python3 /opt/mascarade/mascarade_ai.py process '{json.dumps(task)}'"
    
    # Tester sur le nœud kxkm (bon pour l'inférence)
    print("\n🔄 Traitement sur kxkm@kxkm-ai...")
    stdout, stderr, code = execute_ssh_command("kxkm@kxkm-ai", command)
    
    if code == 0:
        result = json.loads(stdout)
        print("\n✅ Résultat :")
        print(json.dumps(result, indent=2))
    else:
        print(f"❌ Erreur : {stderr}")

def demo_parallel_processing():
    """Démonstration du traitement parallèle"""
    print("\n" + "=" * 60)
    print("⚡ DÉMONSTRATION : TRAITEMENT PARALLÈLE")
    print("=" * 60)
    
    tasks = [
        {
            "id": f"parallel-{i}",
            "title": f"Tâche parallèle #{i}",
            "description": f"Traitement distribué numéro {i}",
            "capability": "textProcessing"
        }
        for i in range(1, 4)
    ]
    
    nodes = [
        "root@192.168.0.119",
        "clems@192.168.0.120",
        "kxkm@kxkm-ai"
    ]
    
    print(f"\n📤 Envoi de {len(tasks)} tâches en parallèle...")
    print(f"🌐 Sur {len(nodes)} nœuds différents")
    
    import concurrent.futures
    
    def process_task(task, node):
        command = f"python3 /opt/mascarade/mascarade_ai.py process '{json.dumps(task)}'"
        stdout, stderr, code = execute_ssh_command(node, command)
        return {
            "task": task["id"],
            "node": node,
            "success": code == 0,
            "result": stdout if code == 0 else stderr
        }
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(nodes)) as executor:
        futures = []
        for i, (task, node) in enumerate(zip(tasks, nodes)):
            print(f"  ➡️  {task['id']} → {node}")
            future = executor.submit(process_task, task, node)
            futures.append(future)
        
        print("\n⏳ Traitement en cours...\n")
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['task']} sur {result['node']}")
            if result["success"]:
                data = json.loads(result["result"])
                print(f"   └─ Statut : {data.get('status', 'unknown')}")

def check_node_status():
    """Vérifie le statut de tous les nœuds"""
    print("=" * 60)
    print("🔍 VÉRIFICATION DU STATUT DES NŒUDS")
    print("=" * 60)
    
    nodes = {
        "Root Server": "root@192.168.0.119",
        "Clems Workstation": "clems@192.168.0.120",
        "KXKM AI Node": "kxkm@kxkm-ai",
        "CILS Node": "user@cils"
    }
    
    command = "python3 /opt/mascarade/mascarade_ai.py status"
    
    for name, host in nodes.items():
        print(f"\n📡 {name} ({host})")
        stdout, stderr, code = execute_ssh_command(host, command)
        
        if code == 0:
            try:
                status = json.loads(stdout)
                print(f"   ✅ En ligne")
                print(f"   🖥️  Node ID : {status.get('node_id', 'unknown')}")
                print(f"   ⚡ Charge : {status.get('load', 0):.2%}")
                print(f"   🎯 Capacités : {', '.join(status.get('capabilities', []))}")
            except json.JSONDecodeError:
                print(f"   ⚠️  Réponse invalide")
        else:
            print(f"   ❌ Hors ligne ou erreur")
            if stderr:
                print(f"   └─ {stderr.strip()}")

def demo_capabilities():
    """Liste les capacités de chaque nœud"""
    print("\n" + "=" * 60)
    print("🎯 CAPACITÉS DES NŒUDS")
    print("=" * 60)
    
    nodes = {
        "root@192.168.0.119": "Root Server",
        "clems@192.168.0.120": "Clems Workstation",
        "kxkm@kxkm-ai": "KXKM AI Node",
        "user@cils": "CILS Node"
    }
    
    command = "python3 /opt/mascarade/mascarade_ai.py capabilities"
    
    all_capabilities = {}
    
    for host, name in nodes.items():
        stdout, stderr, code = execute_ssh_command(host, command)
        
        if code == 0:
            try:
                data = json.loads(stdout)
                caps = data.get('capabilities', [])
                all_capabilities[name] = caps
                
                print(f"\n📍 {name}")
                if caps:
                    for cap in caps:
                        print(f"   ✓ {cap}")
                else:
                    print(f"   ⚠️  Aucune capacité détectée")
            except json.JSONDecodeError:
                print(f"\n📍 {name}: Erreur de parsing")
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES CAPACITÉS")
    print("=" * 60)
    
    all_caps_set = set()
    for caps in all_capabilities.values():
        all_caps_set.update(caps)
    
    for cap in sorted(all_caps_set):
        nodes_with_cap = [name for name, caps in all_capabilities.items() if cap in caps]
        print(f"\n🎯 {cap}")
        print(f"   └─ Disponible sur : {', '.join(nodes_with_cap)}")

def main():
    """Menu principal"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║         🤖 DÉMONSTRATIONS IA MASCARADE P2P                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    
Sélectionnez une démonstration :

1. 📝 Traitement de texte
2. 📊 Traitement de données
3. 🧠 Inférence IA
4. ⚡ Traitement parallèle
5. 🔍 Vérification du statut des nœuds
6. 🎯 Capacités des nœuds
7. 🚀 Tout exécuter

0. Quitter
""")
    
    while True:
        try:
            choice = input("\n👉 Votre choix (0-7) : ").strip()
            
            if choice == "0":
                print("\n👋 Au revoir !\n")
                break
            elif choice == "1":
                demo_text_processing()
            elif choice == "2":
                demo_data_processing()
            elif choice == "3":
                demo_inference()
            elif choice == "4":
                demo_parallel_processing()
            elif choice == "5":
                check_node_status()
            elif choice == "6":
                demo_capabilities()
            elif choice == "7":
                check_node_status()
                demo_capabilities()
                demo_text_processing()
                demo_data_processing()
                demo_inference()
                demo_parallel_processing()
                print("\n" + "=" * 60)
                print("🎉 TOUTES LES DÉMONSTRATIONS TERMINÉES !")
                print("=" * 60)
            else:
                print("❌ Choix invalide. Essayez encore.")
            
            input("\n⏎ Appuyez sur Entrée pour continuer...")
            
        except KeyboardInterrupt:
            print("\n\n👋 Au revoir !\n")
            break
        except Exception as e:
            print(f"\n❌ Erreur : {e}\n")

if __name__ == "__main__":
    # Vérifier que les dépendances sont disponibles
    try:
        import concurrent.futures
    except ImportError:
        print("❌ Module concurrent.futures requis")
        sys.exit(1)
    
    main()
