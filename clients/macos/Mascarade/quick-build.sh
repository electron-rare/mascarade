#!/bin/bash

# quick-build.sh
# Build et lancement rapide

set -e

echo "🔨 Building KanbanAI..."
echo ""

# Build
swift build

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    
    # Afficher l'exécutable
    BINARY=".build/debug/KanbanAI"
    if [ -f "$BINARY" ]; then
        SIZE=$(du -h "$BINARY" | cut -f1)
        echo "📦 Binary: $BINARY ($SIZE)"
        echo ""
        
        # Lancer
        echo "🚀 Running KanbanAI..."
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        "$BINARY"
        
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi
else
    echo ""
    echo "❌ Build failed"
    exit 1
fi
