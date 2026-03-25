#!/bin/bash

# run.sh
# Script rapide pour lancer l'application

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Lancement de KanbanAI...${NC}"
echo ""

# Vérifier si l'app est buildée
BINARY=".build/debug/KanbanAI"

if [ ! -f "$BINARY" ]; then
    echo -e "${YELLOW}⚠️  Application non buildée, compilation en cours...${NC}"
    swift build
    echo ""
fi

# Lancer
echo -e "${GREEN}✓ Lancement...${NC}"
echo ""

exec "$BINARY"
