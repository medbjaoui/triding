#!/bin/bash
# Double-cliquez : mesure sur données réelles la fréquence d'un gain de +50% en 4h.
# Lecture seule — aucun ordre n'est passé.
cd "$(dirname "$0")" || exit 1
if [ ! -d "venv" ]; then
    echo "❌ Lancez d'abord LANCER_TEST.command"
    read -n 1 -s -r -p "Appuyez sur une touche..."; exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo ""
echo "Analyse de 12 coins sur 1 an (2 à 3 minutes). Aucun ordre ne sera passé."
python3 base_rate.py
read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
