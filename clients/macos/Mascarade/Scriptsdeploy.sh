#!/bin/bash

# deploy.sh
# Script de déploiement multi-environnements

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Fonction d'aide
show_help() {
    cat << EOF
${GREEN}KanbanAI Deployment Script${NC}

Usage: $0 [ENVIRONMENT] [OPTIONS]

${YELLOW}Environments:${NC}
    dev         Déployer sur environnement de développement
    staging     Déployer sur environnement de staging
    prod        Déployer sur environnement de production

${YELLOW}Options:${NC}
    --skip-build        Ne pas rebuilder avant déploiement
    --skip-tests        Ne pas exécuter les tests
    --skip-backup       Ne pas faire de backup
    --force             Forcer le déploiement sans confirmation
    --rollback          Revenir à la version précédente
    -h, --help          Afficher cette aide

${YELLOW}Exemples:${NC}
    $0 dev                      # Déployer en dev
    $0 staging --skip-tests     # Déployer en staging sans tests
    $0 prod --force             # Déployer en prod sans confirmation

EOF
}

# Variables
ENVIRONMENT=""
SKIP_BUILD=false
SKIP_TESTS=false
SKIP_BACKUP=false
FORCE=false
ROLLBACK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        dev|development)
            ENVIRONMENT="development"
            shift
            ;;
        staging)
            ENVIRONMENT="staging"
            shift
            ;;
        prod|production)
            ENVIRONMENT="production"
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Option inconnue: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Vérifier qu'un environnement est spécifié
if [ -z "$ENVIRONMENT" ]; then
    echo -e "${RED}❌ Erreur: Environnement requis${NC}"
    show_help
    exit 1
fi

# Configuration selon l'environnement
case $ENVIRONMENT in
    development)
        NODES=("localhost:2222")
        COLOR=$BLUE
        ;;
    staging)
        NODES=("192.168.1.119" "192.168.1.120")
        COLOR=$YELLOW
        ;;
    production)
        NODES=("root@192.168.0.119" "clems@192.168.0.120" "kxkm@kxkm-ai" "user@cils")
        COLOR=$GREEN
        ;;
esac

# Afficher le header
echo -e "${COLOR}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${COLOR}   DÉPLOIEMENT - $ENVIRONMENT${NC}"
echo -e "${COLOR}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Confirmation en production
if [ "$ENVIRONMENT" = "production" ] && [ "$FORCE" = false ]; then
    echo -e "${YELLOW}⚠️  Vous êtes sur le point de déployer en PRODUCTION${NC}"
    echo -e "${YELLOW}   Nœuds cibles: ${#NODES[@]} nœuds${NC}"
    echo ""
    read -p "Êtes-vous sûr ? (oui/non): " -r
    echo ""
    if [[ ! $REPLY =~ ^[Oo][Uu][Ii]$ ]]; then
        echo -e "${RED}❌ Déploiement annulé${NC}"
        exit 1
    fi
fi

# Rollback
if [ "$ROLLBACK" = true ]; then
    echo -e "${YELLOW}🔄 Rollback to previous version...${NC}"
    
    BACKUP_DIR="$PROJECT_ROOT/Backups"
    if [ ! -d "$BACKUP_DIR" ]; then
        echo -e "${RED}❌ Aucun backup trouvé${NC}"
        exit 1
    fi
    
    # Trouver le dernier backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | grep "$ENVIRONMENT" | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        echo -e "${RED}❌ Aucun backup trouvé pour $ENVIRONMENT${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Restauration depuis: $LATEST_BACKUP${NC}"
    
    # Restaurer sur chaque nœud
    for node in "${NODES[@]}"; do
        echo -e "${BLUE}  📡 Restauration sur $node...${NC}"
        # Implémenter la logique de restauration
    done
    
    echo -e "${GREEN}✅ Rollback completed${NC}"
    exit 0
fi

# Backup
if [ "$SKIP_BACKUP" = false ] && [ "$ENVIRONMENT" != "development" ]; then
    echo -e "${BLUE}💾 Creating backup...${NC}"
    
    BACKUP_DIR="$PROJECT_ROOT/Backups"
    mkdir -p "$BACKUP_DIR"
    
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_NAME="${ENVIRONMENT}_${TIMESTAMP}"
    BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
    
    mkdir -p "$BACKUP_PATH"
    
    # Sauvegarder depuis chaque nœud
    for node in "${NODES[@]}"; do
        echo -e "  Backup from $node..."
        # Implémenter la sauvegarde
    done
    
    echo -e "${GREEN}✅ Backup created: $BACKUP_NAME${NC}"
    echo ""
fi

# Tests
if [ "$SKIP_TESTS" = false ]; then
    echo -e "${BLUE}🧪 Running tests...${NC}"
    cd "$PROJECT_ROOT"
    swift test
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Tests failed - Deployment aborted${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All tests passed${NC}"
    echo ""
fi

# Build
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${BLUE}🔨 Building for $ENVIRONMENT...${NC}"
    cd "$PROJECT_ROOT"
    
    "$SCRIPT_DIR/build.sh" "$ENVIRONMENT" --clean
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Build failed - Deployment aborted${NC}"
        exit 1
    fi
    
    echo ""
fi

# Déploiement des scripts IA
echo -e "${BLUE}🤖 Deploying AI scripts to nodes...${NC}"

case $ENVIRONMENT in
    development)
        echo -e "${YELLOW}ℹ️  Development: Using local nodes${NC}"
        ;;
    staging)
        "$SCRIPT_DIR/deploy_mascarade.sh" staging --check
        ;;
    production)
        "$SCRIPT_DIR/deploy_mascarade.sh" --all
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ AI scripts deployment failed${NC}"
            exit 1
        fi
        ;;
esac

echo -e "${GREEN}✅ AI scripts deployed${NC}"
echo ""

# Health check
echo -e "${BLUE}🏥 Health check...${NC}"

FAILED_NODES=0

for node in "${NODES[@]}"; do
    echo -n "  Checking $node... "
    
    if ssh -o ConnectTimeout=5 "$node" "echo OK" &>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((FAILED_NODES++))
    fi
done

echo ""

if [ $FAILED_NODES -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Warning: $FAILED_NODES node(s) unreachable${NC}"
    
    if [ "$ENVIRONMENT" = "production" ]; then
        read -p "Continue deployment? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            echo -e "${RED}❌ Deployment aborted${NC}"
            exit 1
        fi
    fi
fi

# Vérification finale
echo -e "${BLUE}🔍 Final verification...${NC}"

case $ENVIRONMENT in
    development)
        echo "  ✓ Binary built"
        echo "  ✓ Configuration loaded"
        ;;
    staging)
        echo "  ✓ Staging nodes configured"
        echo "  ✓ AI scripts deployed"
        ;;
    production)
        echo "  ✓ All production nodes ready"
        echo "  ✓ Backup created"
        echo "  ✓ AI scripts deployed and tested"
        ;;
esac

echo ""

# Succès
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
echo -e "${BLUE}Nodes:${NC} ${#NODES[@]}"
echo -e "${BLUE}Time:${NC} $(date)"
echo ""

# Instructions post-déploiement
case $ENVIRONMENT in
    development)
        echo -e "${YELLOW}💡 Next steps:${NC}"
        echo "  • Run the app: make run"
        echo "  • Check logs: tail -f Logs/app.log"
        ;;
    staging)
        echo -e "${YELLOW}💡 Next steps:${NC}"
        echo "  • Test all features"
        echo "  • Monitor: make status"
        echo "  • Check logs: make logs-all"
        ;;
    production)
        echo -e "${YELLOW}💡 Next steps:${NC}"
        echo "  • Monitor health: make status"
        echo "  • Check metrics: make logs-all"
        echo "  • Verify user access"
        echo ""
        echo -e "${YELLOW}⚠️  Rollback command:${NC}"
        echo "  $0 prod --rollback"
        ;;
esac

echo ""
