#!/bin/bash
# Double-cliquez pour comparer la stratégie sur plusieurs cryptos.
# Lecture seule : aucun ordre n'est passé, votre argent n'est pas touché.

cd "$(dirname "$0")" || exit 1

if [ ! -d "venv" ]; then
    echo "❌ Environnement non installé."
    echo "   Double-cliquez d'abord sur LANCER_TEST.command"
    read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo ""
echo "Chargement de l'historique depuis Binance (1 à 2 minutes)..."
echo "Aucun ordre ne sera passé — analyse uniquement."
echo ""

python3 backtest.py "$@"

read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
