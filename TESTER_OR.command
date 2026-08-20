#!/bin/bash
# Double-cliquez : teste la stratégie sur l'or tokenisé (PAXG, XAUT) et compare au BTC.
# Lecture seule — aucun ordre n'est passé.

cd "$(dirname "$0")" || exit 1
if [ ! -d "venv" ]; then
    echo "❌ Lancez d'abord LANCER_TEST.command"
    read -n 1 -s -r -p "Appuyez sur une touche..."; exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo ""
echo "=== Or tokenisé vs crypto — bougies 1 jour, 2 ans ==="
echo "Aucun ordre ne sera passé."
echo ""
python3 backtest.py --coins PAXG,XAUT,BTC,ETH --tf 1d --jours 730

echo ""
echo "=== Comparaison sur bougies 4h ==="
echo ""
python3 backtest.py --coins PAXG,XAUT,BTC --tf 4h --jours 730

read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
