#!/bin/bash
# Double-cliquez : état du marché et probabilités historiques.
# Lecture seule — aucun ordre n'est passé.
cd "$(dirname "$0")" || exit 1
if [ ! -d "venv" ]; then
    echo "❌ Lancez d'abord LANCER_TEST.command"
    read -n 1 -s -r -p "Appuyez sur une touche..."; exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate
python3 contexte_marche.py "$@"
read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
