#!/bin/bash

# make-executable.sh
# Rend tous les scripts exécutables

echo "🔧 Rendre les scripts exécutables..."

chmod +x Scripts/*.sh 2>/dev/null
chmod +x Scripts/*.py 2>/dev/null
chmod +x run.sh 2>/dev/null

echo "✅ Terminé !"
echo ""
echo "Scripts exécutables:"
ls -lh Scripts/*.sh Scripts/*.py run.sh 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
