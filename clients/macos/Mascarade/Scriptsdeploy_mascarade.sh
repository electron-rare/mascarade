#!/bin/bash

# deploy_mascarade.sh
# Script de déploiement du système IA Mascarade sur les nœuds P2P

set -e

# Configuration des nœuds
declare -A NODES=(
    ["root"]="root@192.168.0.119"
    ["clems"]="clems@192.168.0.120"
    ["kxkm"]="kxkm@kxkm-ai"
    ["cils"]="user@cils"
)

SCRIPT_PATH="./mascarade_ai.py"
REMOTE_PATH="/opt/mascarade/mascarade_ai.py"
LOG_DIR="/var/log/mascarade"

echo "🚀 Déploiement du système IA Mascarade P2P"
echo "=========================================="

# Fonction pour déployer sur un nœud
deploy_to_node() {
    local node_name=$1
    local node_address=$2
    
    echo ""
    echo "📡 Déploiement sur $node_name ($node_address)..."
    
    # Créer le répertoire distant
    ssh "$node_address" "mkdir -p /opt/mascarade && mkdir -p $LOG_DIR" 2>/dev/null || {
        echo "❌ Erreur: Impossible de se connecter à $node_name"
        return 1
    }
    
    # Copier le script Python
    scp "$SCRIPT_PATH" "$node_address:$REMOTE_PATH" 2>/dev/null || {
        echo "❌ Erreur: Impossible de copier le script sur $node_name"
        return 1
    }
    
    # Rendre le script exécutable
    ssh "$node_address" "chmod +x $REMOTE_PATH"
    
    # Installer les dépendances Python (optionnel)
    echo "  📦 Installation des dépendances Python..."
    ssh "$node_address" "python3 -m pip install --quiet numpy pillow 2>/dev/null || true"
    
    # Tester le déploiement
    echo "  🔍 Test de connexion..."
    local status=$(ssh "$node_address" "python3 $REMOTE_PATH status" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Déploiement réussi sur $node_name"
        echo "  📊 Statut: $status" | head -n 3
    else
        echo "  ⚠️  Déploiement terminé mais le test a échoué"
    fi
    
    return 0
}

# Fonction pour vérifier les prérequis
check_prerequisites() {
    echo "🔍 Vérification des prérequis..."
    
    if [ ! -f "$SCRIPT_PATH" ]; then
        echo "❌ Erreur: Script mascarade_ai.py introuvable"
        exit 1
    fi
    
    if ! command -v ssh &> /dev/null; then
        echo "❌ Erreur: SSH non installé"
        exit 1
    fi
    
    if ! command -v scp &> /dev/null; then
        echo "❌ Erreur: SCP non installé"
        exit 1
    fi
    
    echo "✅ Prérequis validés"
}

# Fonction pour créer un service systemd (optionnel)
create_systemd_service() {
    local node_address=$1
    local service_content="[Unit]
Description=Mascarade AI Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $REMOTE_PATH daemon
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/service.log
StandardError=append:$LOG_DIR/error.log

[Install]
WantedBy=multi-user.target"

    echo "$service_content" | ssh "$node_address" "cat > /tmp/mascarade-ai.service"
    ssh "$node_address" "sudo mv /tmp/mascarade-ai.service /etc/systemd/system/ && sudo systemctl daemon-reload"
    
    echo "  🔧 Service systemd créé (utilisez 'sudo systemctl start mascarade-ai' pour démarrer)"
}

# Fonction pour afficher l'aide
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] [NODES]

Options:
    --all           Déployer sur tous les nœuds
    --systemd       Créer un service systemd sur les nœuds
    --check         Vérifier uniquement l'état des nœuds
    --help          Afficher cette aide

Nœuds disponibles:
    root            root@192.168.0.119
    clems           clems@192.168.0.120
    kxkm            kxkm@kxkm-ai
    cils            user@cils

Exemples:
    $0 --all                    # Déployer sur tous les nœuds
    $0 root clems               # Déployer sur root et clems uniquement
    $0 --check                  # Vérifier l'état de tous les nœuds
    $0 --systemd --all          # Déployer avec service systemd

EOF
}

# Fonction pour vérifier l'état des nœuds
check_nodes() {
    echo "🔍 Vérification de l'état des nœuds..."
    echo ""
    
    for node_name in "${!NODES[@]}"; do
        node_address="${NODES[$node_name]}"
        echo "📡 $node_name ($node_address):"
        
        if ssh -o ConnectTimeout=5 "$node_address" "python3 $REMOTE_PATH status" 2>/dev/null; then
            echo "  ✅ Nœud opérationnel"
        else
            echo "  ❌ Nœud inaccessible ou non configuré"
        fi
        echo ""
    done
}

# Parsing des arguments
USE_SYSTEMD=false
CHECK_ONLY=false
DEPLOY_ALL=false
SELECTED_NODES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            show_help
            exit 0
            ;;
        --all)
            DEPLOY_ALL=true
            shift
            ;;
        --systemd)
            USE_SYSTEMD=true
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        *)
            if [[ -n "${NODES[$1]}" ]]; then
                SELECTED_NODES+=("$1")
            else
                echo "❌ Nœud inconnu: $1"
                echo "Utilisez --help pour voir les nœuds disponibles"
                exit 1
            fi
            shift
            ;;
    esac
done

# Mode vérification uniquement
if [ "$CHECK_ONLY" = true ]; then
    check_nodes
    exit 0
fi

# Vérification des prérequis
check_prerequisites

# Déterminer quels nœuds déployer
if [ "$DEPLOY_ALL" = true ]; then
    SELECTED_NODES=("${!NODES[@]}")
elif [ ${#SELECTED_NODES[@]} -eq 0 ]; then
    echo "❌ Aucun nœud spécifié. Utilisez --all ou spécifiez des nœuds."
    echo "Utilisez --help pour plus d'informations"
    exit 1
fi

# Déploiement
SUCCESSFUL=0
FAILED=0

for node_name in "${SELECTED_NODES[@]}"; do
    node_address="${NODES[$node_name]}"
    
    if deploy_to_node "$node_name" "$node_address"; then
        ((SUCCESSFUL++))
        
        # Créer le service systemd si demandé
        if [ "$USE_SYSTEMD" = true ]; then
            echo "  🔧 Configuration du service systemd..."
            create_systemd_service "$node_address" || echo "  ⚠️  Impossible de créer le service systemd"
        fi
    else
        ((FAILED++))
    fi
done

# Résumé
echo ""
echo "=========================================="
echo "📊 Résumé du déploiement"
echo "=========================================="
echo "✅ Réussis: $SUCCESSFUL"
echo "❌ Échoués: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 Déploiement terminé avec succès!"
    echo ""
    echo "Pour tester le système:"
    echo "  ssh root@192.168.0.119 'python3 $REMOTE_PATH status'"
    echo ""
    echo "Pour traiter une tâche:"
    echo "  ssh root@192.168.0.119 'python3 $REMOTE_PATH process \"{\\\"id\\\":\\\"test\\\",\\\"title\\\":\\\"Test\\\",\\\"capability\\\":\\\"textProcessing\\\"}\"'"
else
    echo "⚠️  Certains déploiements ont échoué"
    exit 1
fi
