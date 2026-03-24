#!/bin/bash

# build.sh
# Script de build multi-environnements pour KanbanAI

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="KanbanAI"
SCHEME="KanbanAI"

# Fonction d'aide
show_help() {
    cat << EOF
${GREEN}KanbanAI Build Script${NC}

Usage: $0 [ENVIRONMENT] [OPTIONS]

${YELLOW}Environments:${NC}
    dev, development    Build pour développement (DEBUG)
    staging             Build pour staging
    prod, production    Build pour production (RELEASE)

${YELLOW}Options:${NC}
    --clean             Nettoyer avant de builder
    --test              Exécuter les tests
    --archive           Créer une archive
    --run               Lancer après le build
    -h, --help          Afficher cette aide

${YELLOW}Exemples:${NC}
    $0 dev              # Build développement
    $0 prod --clean     # Build production avec nettoyage
    $0 staging --test   # Build staging avec tests

EOF
}

# Parse des arguments
ENVIRONMENT="development"
CLEAN=false
RUN_TESTS=false
ARCHIVE=false
RUN_APP=false

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
        --clean)
            CLEAN=true
            shift
            ;;
        --test)
            RUN_TESTS=true
            shift
            ;;
        --archive)
            ARCHIVE=true
            shift
            ;;
        --run)
            RUN_APP=true
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

# Déterminer la configuration de build
case $ENVIRONMENT in
    development)
        CONFIGURATION="Debug"
        SWIFT_FLAGS="-DDEBUG"
        echo -e "${BLUE}🔨 Building for DEVELOPMENT${NC}"
        ;;
    staging)
        CONFIGURATION="Release"
        SWIFT_FLAGS="-DSTAGING"
        echo -e "${YELLOW}🔨 Building for STAGING${NC}"
        ;;
    production)
        CONFIGURATION="Release"
        SWIFT_FLAGS=""
        echo -e "${GREEN}🔨 Building for PRODUCTION${NC}"
        ;;
esac

# Afficher la configuration
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Environment    : $ENVIRONMENT"
echo "  Configuration  : $CONFIGURATION"
echo "  Clean          : $CLEAN"
echo "  Run Tests      : $RUN_TESTS"
echo "  Archive        : $ARCHIVE"
echo "  Run After Build: $RUN_APP"
echo ""

# Nettoyer si demandé
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}🧹 Cleaning...${NC}"
    swift package clean
    rm -rf .build
    echo -e "${GREEN}✅ Clean completed${NC}"
    echo ""
fi

# Exécuter les tests si demandé
if [ "$RUN_TESTS" = true ]; then
    echo -e "${BLUE}🧪 Running tests...${NC}"
    swift test
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ All tests passed${NC}"
    else
        echo -e "${RED}❌ Tests failed${NC}"
        exit 1
    fi
    echo ""
fi

# Build
echo -e "${BLUE}🔨 Building $APP_NAME...${NC}"

if [ -n "$SWIFT_FLAGS" ]; then
    swift build -c $CONFIGURATION -Xswiftc "$SWIFT_FLAGS"
else
    swift build -c $CONFIGURATION
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful${NC}"
else
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

# Localiser le binaire
BINARY_PATH=".build/$CONFIGURATION/$APP_NAME"

if [ -f "$BINARY_PATH" ]; then
    echo ""
    echo -e "${GREEN}📦 Binary location:${NC} $BINARY_PATH"
    
    # Afficher la taille
    SIZE=$(du -h "$BINARY_PATH" | cut -f1)
    echo -e "${BLUE}   Size:${NC} $SIZE"
fi

# Créer une archive si demandé
if [ "$ARCHIVE" = true ]; then
    echo ""
    echo -e "${YELLOW}📦 Creating archive...${NC}"
    
    ARCHIVE_DIR="Archives"
    mkdir -p "$ARCHIVE_DIR"
    
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    ARCHIVE_NAME="${APP_NAME}_${ENVIRONMENT}_${TIMESTAMP}"
    ARCHIVE_PATH="$ARCHIVE_DIR/$ARCHIVE_NAME"
    
    mkdir -p "$ARCHIVE_PATH"
    
    # Copier le binaire
    cp "$BINARY_PATH" "$ARCHIVE_PATH/"
    
    # Copier la configuration
    cp -r Config "$ARCHIVE_PATH/" 2>/dev/null || true
    
    # Copier les scripts
    cp -r Scripts "$ARCHIVE_PATH/" 2>/dev/null || true
    
    # Créer un README
    cat > "$ARCHIVE_PATH/README.txt" << EOF
$APP_NAME - $ENVIRONMENT Build
Built on: $(date)
Configuration: $CONFIGURATION
Environment: $ENVIRONMENT

To run:
  ./$APP_NAME

To deploy AI scripts:
  cd Scripts
  ./deploy_mascarade.sh --all
EOF
    
    # Compresser
    tar -czf "${ARCHIVE_PATH}.tar.gz" -C "$ARCHIVE_DIR" "$ARCHIVE_NAME"
    rm -rf "$ARCHIVE_PATH"
    
    echo -e "${GREEN}✅ Archive created:${NC} ${ARCHIVE_PATH}.tar.gz"
fi

# Copier la configuration de l'environnement
echo ""
echo -e "${BLUE}📝 Setting up environment configuration...${NC}"

# Créer un fichier .env pour l'environnement actuel
cat > .env << EOF
# Environment Configuration
ENVIRONMENT=$ENVIRONMENT
CONFIGURATION=$CONFIGURATION
BUILD_DATE=$(date -Iseconds)
EOF

echo -e "${GREEN}✅ Environment file created: .env${NC}"

# Lancer l'application si demandé
if [ "$RUN_APP" = true ]; then
    echo ""
    echo -e "${GREEN}🚀 Launching $APP_NAME...${NC}"
    echo ""
    
    if [ -f "$BINARY_PATH" ]; then
        "$BINARY_PATH"
    else
        echo -e "${RED}❌ Binary not found: $BINARY_PATH${NC}"
        exit 1
    fi
fi

# Résumé final
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Build completed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Environment:${NC} $ENVIRONMENT"
echo -e "${BLUE}Binary:${NC} $BINARY_PATH"
echo ""

case $ENVIRONMENT in
    development)
        echo -e "${YELLOW}💡 Development Tips:${NC}"
        echo "  • Debug logging is enabled"
        echo "  • Use local nodes (localhost:2222)"
        echo "  • Run tests: swift test"
        echo "  • Quick run: make run"
        ;;
    staging)
        echo -e "${YELLOW}💡 Staging Tips:${NC}"
        echo "  • Test on staging nodes (192.168.1.x)"
        echo "  • Verify all features before production"
        echo "  • Check logs: make logs-all"
        ;;
    production)
        echo -e "${YELLOW}💡 Production Tips:${NC}"
        echo "  • Deploy to production nodes"
        echo "  • Monitor logs: make logs-all"
        echo "  • Check health: make status"
        echo "  • Backup before deploy"
        ;;
esac

echo ""
