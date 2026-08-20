#!/bin/bash
# Double-cliquez pour démarrer le bot. Fermez la fenêtre pour l'arrêter.

cd "$(dirname "$0")" || exit 1

echo ""
echo "==================================================="
echo "   Démarrage du bot de trading"
echo "==================================================="
echo ""

if [ ! -d "venv" ]; then
    echo "❌ Environnement non installé."
    echo "   Double-cliquez d'abord sur LANCER_TEST.command"
    echo ""
    read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

MODE=$(grep -E '^DRY_RUN=' .env 2>/dev/null | cut -d= -f2 | tr -d ' \r')
if [ "$MODE" = "false" ]; then
    echo "⚠️  MODE RÉEL — le bot va engager votre argent."
    echo ""
    read -r -p "Tapez OUI en majuscules pour confirmer : " REPONSE
    if [ "$REPONSE" != "OUI" ]; then
        echo "Annulé. Le bot n'a pas démarré."
        read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
        exit 0
    fi
else
    echo "✅ Mode SIMULATION (dry-run) — aucun ordre réel ne sera passé."
fi

echo ""
echo "Le bot vérifie le marché toutes les 15 minutes."
echo "⚠️  Gardez cette fenêtre OUVERTE et le Mac allumé."
echo "   Pour arrêter : Ctrl+C, ou fermez la fenêtre."
echo ""
echo "---------------------------------------------------"
echo ""

python3 bot.py

echo ""
echo "Le bot s'est arrêté."
read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
echo ""
