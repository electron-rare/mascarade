#!/bin/bash

# setup-app.sh
# Script de configuration initiale de l'application KanbanAI

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}║         ${GREEN}KanbanAI${BLUE} - Application Setup                      ║${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Vérifier les prérequis
echo -e "${GREEN}📋 Vérification des prérequis...${NC}"
echo ""

# Swift
if command -v swift &> /dev/null; then
    SWIFT_VERSION=$(swift --version | head -n 1)
    echo -e "  ✓ Swift: $SWIFT_VERSION"
else
    echo -e "  ${RED}✗ Swift non installé${NC}"
    echo -e "    Installer Xcode Command Line Tools"
    exit 1
fi

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "  ✓ Python: $PYTHON_VERSION"
else
    echo -e "  ${YELLOW}⚠ Python3 non installé (optionnel pour IA)${NC}"
fi

# SSH
if command -v ssh &> /dev/null; then
    echo -e "  ✓ SSH: Installé"
else
    echo -e "  ${RED}✗ SSH non disponible${NC}"
    exit 1
fi

echo ""

# 2. Créer la structure de répertoires
echo -e "${GREEN}📁 Création de la structure de répertoires...${NC}"

mkdir -p Sources/{Core/{Models,Services,Config,ViewModels},UI/Views}
mkdir -p Tests
mkdir -p Scripts
mkdir -p Config
mkdir -p Logs
mkdir -p Archives
mkdir -p Backups

echo -e "  ✓ Répertoires créés"
echo ""

# 3. Rendre les scripts exécutables
echo -e "${GREEN}🔧 Configuration des scripts...${NC}"

if [ -d Scripts ]; then
    chmod +x Scripts/*.sh 2>/dev/null || true
    chmod +x Scripts/*.py 2>/dev/null || true
    echo -e "  ✓ Scripts rendus exécutables"
fi

echo ""

# 4. Créer la configuration initiale
echo -e "${GREEN}⚙️  Création de la configuration initiale...${NC}"

# .env
cat > .env << EOF
# Environment Configuration
ENVIRONMENT=development
CONFIGURATION=Debug
BUILD_DATE=$(date -Iseconds)
SETUP_DATE=$(date)
EOF

echo -e "  ✓ .env créé"

# .gitignore si pas présent
if [ ! -f .gitignore ]; then
    cat > .gitignore << 'EOF'
# Build
.build/
*.xcodeproj
.swiftpm/

# Xcode
xcuserdata/
DerivedData/

# Environment
.env

# Logs
*.log
Logs/

# Backups
Backups/
Archives/

# macOS
.DS_Store

# Python
__pycache__/
*.py[cod]
EOF
    echo -e "  ✓ .gitignore créé"
fi

echo ""

# 5. Résoudre les dépendances Swift
echo -e "${GREEN}📦 Résolution des dépendances Swift...${NC}"

if [ -f Package.swift ]; then
    swift package resolve
    echo -e "  ✓ Dépendances résolues"
else
    echo -e "  ${YELLOW}⚠ Package.swift non trouvé${NC}"
fi

echo ""

# 6. Build initial
echo -e "${GREEN}🔨 Build initial (Development)...${NC}"

swift build -c debug

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Build réussi${NC}"
else
    echo -e "  ${RED}✗ Build échoué${NC}"
    echo -e "    Vérifiez les erreurs ci-dessus"
    exit 1
fi

echo ""

# 7. Vérifier l'exécutable
BINARY_PATH=".build/debug/KanbanAI"
if [ -f "$BINARY_PATH" ]; then
    SIZE=$(du -h "$BINARY_PATH" | cut -f1)
    echo -e "${GREEN}📦 Exécutable créé:${NC}"
    echo -e "   Chemin: $BINARY_PATH"
    echo -e "   Taille: $SIZE"
else
    echo -e "${YELLOW}⚠ Exécutable non trouvé${NC}"
fi

echo ""

# 8. Configuration SSH (optionnel)
echo -e "${BLUE}🔑 Configuration SSH${NC}"
echo ""
echo "Voulez-vous configurer SSH pour les nœuds P2P ? (o/n)"
read -r SETUP_SSH

if [[ $SETUP_SSH =~ ^[Oo]$ ]]; then
    echo ""
    echo -e "${GREEN}Configuration SSH...${NC}"
    
    # Vérifier si une clé existe
    if [ ! -f ~/.ssh/id_ed25519 ] && [ ! -f ~/.ssh/id_rsa ]; then
        echo "Génération d'une nouvelle clé SSH..."
        ssh-keygen -t ed25519 -C "kanban-ai-p2p" -f ~/.ssh/id_ed25519 -N ""
        echo -e "  ✓ Clé SSH générée"
    else
        echo -e "  ✓ Clé SSH existante trouvée"
    fi
    
    echo ""
    echo "Configuration des nœuds (root@192.168.0.119, clems@192.168.0.120, etc.):"
    echo "Exécutez manuellement:"
    echo "  ssh-copy-id root@192.168.0.119"
    echo "  ssh-copy-id clems@192.168.0.120"
    echo "  ssh-copy-id kxkm@kxkm-ai"
    echo "  ssh-copy-id user@cils"
fi

echo ""

# 9. Résumé
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Configuration terminée avec succès !${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}📝 Prochaines étapes:${NC}"
echo ""
echo "1. Lancer l'application:"
echo -e "   ${BLUE}make run${NC}"
echo -e "   ou directement: ${BLUE}.build/debug/KanbanAI${NC}"
echo ""
echo "2. Voir toutes les commandes disponibles:"
echo -e "   ${BLUE}make help${NC}"
echo ""
echo "3. Déployer les scripts IA sur les nœuds:"
echo -e "   ${BLUE}make deploy-ai${NC}"
echo ""
echo "4. Consulter la documentation:"
echo -e "   ${BLUE}cat README.md${NC}"
echo -e "   ${BLUE}cat QUICKSTART.md${NC}"
echo ""

echo -e "${GREEN}📚 Documentation disponible:${NC}"
echo "  • README.md           - Guide complet"
echo "  • QUICKSTART.md       - Démarrage rapide"
echo "  • MULTI_ENV.md        - Multi-environnements"
echo "  • EXAMPLES.md         - Exemples d'utilisation"
echo ""

echo -e "${BLUE}🎯 Commandes utiles:${NC}"
echo "  make dev-run         - Build + Run développement"
echo "  make test            - Exécuter les tests"
echo "  make status          - Vérifier les nœuds"
echo "  make demo            - Lancer les démos"
echo ""

echo -e "${GREEN}Bon développement ! 🚀${NC}"
echo ""
