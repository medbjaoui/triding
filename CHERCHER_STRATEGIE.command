#!/bin/bash
# Double-cliquez : cherche une stratégie rentable avec validation hors échantillon.
# Lecture seule — aucun ordre n'est passé.

cd "$(dirname "$0")" || exit 1
if [ ! -d "venv" ]; then
    echo "❌ Lancez d'abord LANCER_TEST.command"
    read -n 1 -s -r -p "Appuyez sur une touche..."; exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo ""
echo "Recherche en cours — 3 à 6 minutes (chargement de 2 ans d'historique)."
echo "Aucun ordre ne sera passé."
echo ""
python3 explorateur.py "$@"
read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
