# Makefile pour Kanban IA P2P
# Simplifie les opérations courantes de développement et déploiement

.PHONY: help build run test clean deploy deploy-all deploy-check install-deps format lint

# Variables
APP_NAME = KanbanAI
SCRIPT_PATH = Scripts/mascarade_ai.py
DEPLOY_SCRIPT = Scripts/deploy_mascarade.sh
PYTHON = python3
SWIFT = swift

# Couleurs pour la sortie
GREEN  = \033[0;32m
YELLOW = \033[0;33m
RED    = \033[0;31m
NC     = \033[0m # No Color

help: ## Affiche cette aide
	@echo "$(GREEN)Kanban IA P2P - Commandes disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

build: ## Compile l'application Swift
	@echo "$(GREEN)🔨 Compilation de $(APP_NAME)...$(NC)"
	$(SWIFT) build -c release
	@echo "$(GREEN)✅ Compilation terminée$(NC)"

run: ## Lance l'application
	@echo "$(GREEN)🚀 Lancement de $(APP_NAME)...$(NC)"
	$(SWIFT) run

test: ## Exécute les tests
	@echo "$(GREEN)🧪 Exécution des tests...$(NC)"
	$(SWIFT) test
	@echo "$(GREEN)✅ Tests terminés$(NC)"

clean: ## Nettoie les fichiers de build
	@echo "$(YELLOW)🧹 Nettoyage...$(NC)"
	$(SWIFT) package clean
	rm -rf .build
	@echo "$(GREEN)✅ Nettoyage terminé$(NC)"

# Déploiement

deploy-check: ## Vérifie l'état des nœuds P2P
	@echo "$(GREEN)🔍 Vérification des nœuds...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) --check

deploy-all: ## Déploie sur tous les nœuds P2P
	@echo "$(GREEN)🚀 Déploiement sur tous les nœuds...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) --all

deploy-root: ## Déploie uniquement sur root@192.168.0.119
	@echo "$(GREEN)📡 Déploiement sur root...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) root

deploy-clems: ## Déploie uniquement sur clems@192.168.0.120
	@echo "$(GREEN)📡 Déploiement sur clems...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) clems

deploy-kxkm: ## Déploie uniquement sur kxkm@kxkm-ai
	@echo "$(GREEN)📡 Déploiement sur kxkm...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) kxkm

deploy-cils: ## Déploie uniquement sur cils
	@echo "$(GREEN)📡 Déploiement sur cils...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) cils

deploy-systemd: ## Déploie avec service systemd
	@echo "$(GREEN)🔧 Déploiement avec systemd...$(NC)"
	chmod +x $(DEPLOY_SCRIPT)
	./$(DEPLOY_SCRIPT) --systemd --all

# SSH et Tests

ssh-root: ## Connexion SSH à root@192.168.0.119
	ssh root@192.168.0.119

ssh-clems: ## Connexion SSH à clems@192.168.0.120
	ssh clems@192.168.0.120

ssh-kxkm: ## Connexion SSH à kxkm@kxkm-ai
	ssh kxkm@kxkm-ai

ssh-cils: ## Connexion SSH à cils
	ssh user@cils

test-python: ## Teste le script Python localement
	@echo "$(GREEN)🧪 Test du script Python...$(NC)"
	$(PYTHON) $(SCRIPT_PATH) status
	@echo ""
	$(PYTHON) $(SCRIPT_PATH) capabilities

test-remote-root: ## Teste le script sur le nœud root
	@echo "$(GREEN)🧪 Test du nœud root...$(NC)"
	ssh root@192.168.0.119 "python3 /opt/mascarade/mascarade_ai.py status"

test-remote-all: ## Teste tous les nœuds distants
	@echo "$(GREEN)🧪 Test de tous les nœuds...$(NC)"
	@echo "\n$(YELLOW)Nœud: root@192.168.0.119$(NC)"
	@ssh root@192.168.0.119 "python3 /opt/mascarade/mascarade_ai.py status" 2>/dev/null || echo "$(RED)❌ Échec$(NC)"
	@echo "\n$(YELLOW)Nœud: clems@192.168.0.120$(NC)"
	@ssh clems@192.168.0.120 "python3 /opt/mascarade/mascarade_ai.py status" 2>/dev/null || echo "$(RED)❌ Échec$(NC)"
	@echo "\n$(YELLOW)Nœud: kxkm@kxkm-ai$(NC)"
	@ssh kxkm@kxkm-ai "python3 /opt/mascarade/mascarade_ai.py status" 2>/dev/null || echo "$(RED)❌ Échec$(NC)"
	@echo "\n$(YELLOW)Nœud: cils$(NC)"
	@ssh user@cils "python3 /opt/mascarade/mascarade_ai.py status" 2>/dev/null || echo "$(RED)❌ Échec$(NC)"

# Installation

install-deps: ## Installe les dépendances Python sur les nœuds
	@echo "$(GREEN)📦 Installation des dépendances Python...$(NC)"
	@echo "Nœud: root@192.168.0.119"
	@ssh root@192.168.0.119 "pip3 install --quiet numpy pillow transformers torch 2>/dev/null || echo 'Certaines dépendances ont échoué'"
	@echo "Nœud: clems@192.168.0.120"
	@ssh clems@192.168.0.120 "pip3 install --quiet numpy pillow transformers torch 2>/dev/null || echo 'Certaines dépendances ont échoué'"
	@echo "Nœud: kxkm@kxkm-ai"
	@ssh kxkm@kxkm-ai "pip3 install --quiet numpy pillow transformers torch 2>/dev/null || echo 'Certaines dépendances ont échoué'"
	@echo "Nœud: cils"
	@ssh user@cils "pip3 install --quiet numpy pillow transformers torch 2>/dev/null || echo 'Certaines dépendances ont échoué'"
	@echo "$(GREEN)✅ Installation terminée$(NC)"

setup-ssh: ## Configure l'authentification SSH par clé
	@echo "$(GREEN)🔑 Configuration SSH...$(NC)"
	@if [ ! -f ~/.ssh/id_ed25519 ]; then \
		echo "Génération d'une nouvelle clé SSH..."; \
		ssh-keygen -t ed25519 -C "kanban-ai-p2p"; \
	fi
	@echo "Copie de la clé vers les nœuds..."
	@ssh-copy-id root@192.168.0.119 2>/dev/null || echo "root: déjà configuré ou échec"
	@ssh-copy-id clems@192.168.0.120 2>/dev/null || echo "clems: déjà configuré ou échec"
	@ssh-copy-id kxkm@kxkm-ai 2>/dev/null || echo "kxkm: déjà configuré ou échec"
	@ssh-copy-id user@cils 2>/dev/null || echo "cils: déjà configuré ou échec"
	@echo "$(GREEN)✅ Configuration SSH terminée$(NC)"

# Développement

format: ## Formate le code Swift
	@echo "$(GREEN)🎨 Formatage du code...$(NC)"
	@which swift-format > /dev/null && swift-format format -i -r Sources/ Tests/ || echo "$(YELLOW)swift-format non installé$(NC)"

lint: ## Vérifie la qualité du code
	@echo "$(GREEN)🔍 Vérification du code...$(NC)"
	@which swiftlint > /dev/null && swiftlint || echo "$(YELLOW)swiftlint non installé$(NC)"

# Logs

logs-root: ## Affiche les logs du nœud root
	@ssh root@192.168.0.119 "tail -n 50 /var/log/mascarade_ai_*.log 2>/dev/null" || echo "$(RED)Pas de logs disponibles$(NC)"

logs-clems: ## Affiche les logs du nœud clems
	@ssh clems@192.168.0.120 "tail -n 50 /var/log/mascarade_ai_*.log 2>/dev/null" || echo "$(RED)Pas de logs disponibles$(NC)"

logs-kxkm: ## Affiche les logs du nœud kxkm
	@ssh kxkm@kxkm-ai "tail -n 50 /var/log/mascarade_ai_*.log 2>/dev/null" || echo "$(RED)Pas de logs disponibles$(NC)"

logs-cils: ## Affiche les logs du nœud cils
	@ssh user@cils "tail -n 50 /var/log/mascarade_ai_*.log 2>/dev/null" || echo "$(RED)Pas de logs disponibles$(NC)"

logs-all: ## Affiche les logs de tous les nœuds
	@echo "$(GREEN)📋 Logs de tous les nœuds...$(NC)"
	@echo "\n$(YELLOW)=== root@192.168.0.119 ===$(NC)"
	@$(MAKE) logs-root
	@echo "\n$(YELLOW)=== clems@192.168.0.120 ===$(NC)"
	@$(MAKE) logs-clems
	@echo "\n$(YELLOW)=== kxkm@kxkm-ai ===$(NC)"
	@$(MAKE) logs-kxkm
	@echo "\n$(YELLOW)=== cils ===$(NC)"
	@$(MAKE) logs-cils

# Statistiques

stats: ## Affiche des statistiques du projet
	@echo "$(GREEN)📊 Statistiques du projet$(NC)"
	@echo ""
	@echo "$(YELLOW)Fichiers Swift:$(NC)"
	@find Sources -name "*.swift" | wc -l | xargs echo "  "
	@echo "$(YELLOW)Lignes de code Swift:$(NC)"
	@find Sources -name "*.swift" -exec wc -l {} + | tail -1 | awk '{print "  " $$1}'
	@echo "$(YELLOW)Fichiers de tests:$(NC)"
	@find Tests -name "*.swift" | wc -l | xargs echo "  "
	@echo "$(YELLOW)Fichiers Python:$(NC)"
	@find Scripts -name "*.py" | wc -l | xargs echo "  "
	@echo ""

# Documentation

docs: ## Génère la documentation
	@echo "$(GREEN)📚 Génération de la documentation...$(NC)"
	@which swift-docc > /dev/null && swift package generate-documentation || echo "$(YELLOW)swift-docc non installé$(NC)"

# Raccourcis pratiques

dev: build test ## Build + Test rapide
	@echo "$(GREEN)✅ Build et tests terminés$(NC)"

full-deploy: deploy-all install-deps test-remote-all ## Déploiement complet
	@echo "$(GREEN)✅ Déploiement complet terminé$(NC)"

status: test-remote-all ## Affiche le statut de tous les nœuds
	@echo "$(GREEN)✅ Vérification terminée$(NC)"

# Valeur par défaut
.DEFAULT_GOAL := help
