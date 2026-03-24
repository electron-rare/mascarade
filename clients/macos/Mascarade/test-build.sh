#!/bin/bash

# test-build.sh
# Build et test rapide

set -e

echo "🔨 Building and Testing KanbanAI..."
echo ""

# Clean
echo "🧹 Cleaning..."
swift package clean
echo ""

# Resolve dependencies
echo "📦 Resolving dependencies..."
swift package resolve
echo ""

# Build
echo "🔨 Building..."
swift build
echo ""

# Test
echo "🧪 Running tests..."
swift test
echo ""

# Run
echo "🚀 Running application..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

.build/debug/KanbanAI

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ All steps completed successfully!"
