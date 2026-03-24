#!/bin/bash

# env-switch.sh
# Script interactif pour changer d'environnement

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Variables
CURRENT_ENV=""
if [ -f .env ]; then
    CURRENT_ENV=$(grep "ENVIRONMENT=" .env | cut -d'=' -f2)
fi

# Header
clear
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║         ${GREEN}KanbanAI${CYAN} - Environment Switcher                  ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Afficher l'environnement actuel
if [ -n "$CURRENT_ENV" ]; then
    case $CURRENT_ENV in
        development)
            echo -e "${BLUE}Current environment: ${GREEN}Development 🔵${NC}"
            ;;
        staging)
            echo -e "${BLUE}Current environment: ${YELLOW}Staging 🟡${NC}"
            ;;
        production)
            echo -e "${BLUE}Current environment: ${GREEN}Production 🟢${NC}"
            ;;
        *)
            echo -e "${BLUE}Current environment: ${NC}Unknown"
            ;;
    esac
else
    echo -e "${YELLOW}No environment configured yet${NC}"
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Menu
echo -e "${GREEN}Select environment:${NC}"
echo ""
echo -e "  ${BLUE}1)${NC} Development 🔵"
echo -e "     • Local nodes (localhost:2222)"
echo -e "     • Debug logging enabled"
echo -e "     • Quick iteration"
echo ""
echo -e "  ${YELLOW}2)${NC} Staging 🟡"
echo -e "     • Test servers (192.168.1.x)"
echo -e "     • Real conditions testing"
echo -e "     • Metrics enabled"
echo ""
echo -e "  ${GREEN}3)${NC} Production 🟢"
echo -e "     • Production nodes (4 machines)"
echo -e "     • Optimized & secured"
echo -e "     • Full monitoring"
echo ""
echo -e "  ${MAGENTA}4)${NC} Show environment info"
echo ""
echo -e "  ${RED}0)${NC} Exit"
echo ""

# Lire le choix
read -p "Your choice (0-4): " choice

case $choice in
    1)
        TARGET_ENV="development"
        TARGET_COLOR="${BLUE}"
        TARGET_EMOJI="🔵"
        ;;
    2)
        TARGET_ENV="staging"
        TARGET_COLOR="${YELLOW}"
        TARGET_EMOJI="🟡"
        ;;
    3)
        TARGET_ENV="production"
        TARGET_COLOR="${GREEN}"
        TARGET_EMOJI="🟢"
        ;;
    4)
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}Environment Information${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        
        if [ -f .env ]; then
            cat .env
            echo ""
            
            # Lire la config JSON
            if [ -f Config/environments.json ]; then
                echo -e "${BLUE}Configuration details:${NC}"
                python3 -c "
import json
with open('Config/environments.json', 'r') as f:
    config = json.load(f)
    env = '$CURRENT_ENV'
    if env in config:
        data = config[env]
        print(f'  Name: {data[\"name\"]}')
        print(f'  Nodes: {len(data[\"nodes\"])}')
        print(f'  Timeout: {data[\"settings\"][\"connectionTimeout\"]}s')
        print(f'  Retries: {data[\"settings\"][\"retryAttempts\"]}')
        print(f'  Log level: {data[\"settings\"][\"logLevel\"]}')
" 2>/dev/null || echo "  (Config parsing error)"
            fi
        else
            echo "No .env file found"
        fi
        
        echo ""
        read -p "Press Enter to continue..."
        exec "$0"
        ;;
    0)
        echo ""
        echo -e "${GREEN}Bye! 👋${NC}"
        echo ""
        exit 0
        ;;
    *)
        echo ""
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Confirmation
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${TARGET_COLOR}Switching to: $TARGET_ENV $TARGET_EMOJI${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Informations sur l'environnement cible
if [ -f Config/environments.json ]; then
    echo -e "${BLUE}Target configuration:${NC}"
    python3 -c "
import json
with open('Config/environments.json', 'r') as f:
    config = json.load(f)
    env = '$TARGET_ENV'
    if env in config:
        data = config[env]
        print(f'  Nodes: {len(data[\"nodes\"])} configured')
        settings = data['settings']
        print(f'  Timeout: {settings[\"connectionTimeout\"]}s')
        print(f'  Retries: {settings[\"retryAttempts\"]}')
        print(f'  Log level: {settings[\"logLevel\"]}')
        
        # Lister les nœuds
        print(f'\n  Nodes:')
        for node in data['nodes']:
            enabled = '✓' if node['enabled'] else '✗'
            print(f'    {enabled} {node[\"name\"]} ({node[\"host\"]})')
" 2>/dev/null
    echo ""
fi

# Confirmation finale pour production
if [ "$TARGET_ENV" = "production" ]; then
    echo -e "${RED}⚠️  WARNING: You are switching to PRODUCTION${NC}"
    echo ""
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo ""
        echo -e "${YELLOW}Cancelled${NC}"
        exit 0
    fi
    echo ""
fi

# Effectuer le switch
echo -e "${BLUE}Switching environment...${NC}"
echo ""

# 1. Build pour le nouvel environnement
echo -e "${BLUE}1. Building for $TARGET_ENV...${NC}"
make build ENVIRONMENT=$TARGET_ENV

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

# 2. Mettre à jour .env
echo ""
echo -e "${BLUE}2. Updating .env file...${NC}"
cat > .env << EOF
# Environment Configuration
ENVIRONMENT=$TARGET_ENV
CONFIGURATION=$([ "$TARGET_ENV" = "development" ] && echo "Debug" || echo "Release")
BUILD_DATE=$(date -Iseconds)
SWITCHED_AT=$(date)
SWITCHED_BY=${USER}
EOF

echo -e "${GREEN}✓ .env updated${NC}"

# 3. Vérifier les nœuds (sauf pour dev)
if [ "$TARGET_ENV" != "development" ]; then
    echo ""
    echo -e "${BLUE}3. Checking nodes availability...${NC}"
    
    # Extraire et tester les nœuds
    python3 << 'PYTHON_SCRIPT'
import json
import subprocess
import sys

try:
    with open('Config/environments.json', 'r') as f:
        config = json.load(f)
        env = sys.argv[1]
        
        if env in config:
            nodes = config[env]['nodes']
            failed = 0
            
            for node in nodes:
                if not node['enabled']:
                    continue
                    
                host = node['host']
                username = node.get('username', 'user')
                connection = f"{username}@{host}"
                
                print(f"  Testing {connection}...", end=" ")
                
                try:
                    result = subprocess.run(
                        ['ssh', '-o', 'ConnectTimeout=5', connection, 'echo OK'],
                        capture_output=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        print("✓")
                    else:
                        print("✗")
                        failed += 1
                except:
                    print("✗")
                    failed += 1
            
            if failed > 0:
                print(f"\n⚠️  Warning: {failed} node(s) unreachable")
            else:
                print("\n✓ All nodes OK")
                
except Exception as e:
    print(f"Error: {e}")
PYTHON_SCRIPT $TARGET_ENV
fi

# 4. Afficher les prochaines étapes
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Environment switched to: $TARGET_ENV $TARGET_EMOJI${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo ""

case $TARGET_ENV in
    development)
        echo -e "  ${BLUE}1.${NC} Run the app:"
        echo "     make run-dev"
        echo ""
        echo -e "  ${BLUE}2.${NC} Check logs:"
        echo "     tail -f Logs/app.log"
        ;;
    staging)
        echo -e "  ${BLUE}1.${NC} Deploy to staging:"
        echo "     make deploy-staging"
        echo ""
        echo -e "  ${BLUE}2.${NC} Test features"
        echo ""
        echo -e "  ${BLUE}3.${NC} Check status:"
        echo "     make status"
        ;;
    production)
        echo -e "  ${BLUE}1.${NC} Run tests:"
        echo "     make test"
        echo ""
        echo -e "  ${BLUE}2.${NC} Create backup:"
        echo "     make backup"
        echo ""
        echo -e "  ${BLUE}3.${NC} Deploy (when ready):"
        echo "     make deploy-prod"
        echo ""
        echo -e "  ${RED}⚠️${NC}  Remember: Production deployment requires confirmation"
        ;;
esac

echo ""
echo -e "${BLUE}Quick commands:${NC}"
echo "  make status      - Check nodes status"
echo "  make logs-all    - View all logs"
echo "  make help        - See all commands"
echo ""
