#!/bin/bash
# Double-cliquez sur ce fichier dans le Finder pour installer et tester.
# Aucune commande à taper.

cd "$(dirname "$0")" || exit 1

echo ""
echo "==================================================="
echo "   Installation et test du bot de trading"
echo "==================================================="
echo ""

# --- Vérification de Python ---
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3 n'est pas installé sur ce Mac."
    echo "   Installez-le depuis https://www.python.org/downloads/"
    echo ""
    read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
    exit 1
fi
echo "✅ Python 3 détecté : $(python3 --version)"

# --- Environnement virtuel ---
if [ ! -d "venv" ]; then
    echo "⏳ Création de l'environnement virtuel (une seule fois)..."
    if ! python3 -m venv venv; then
        echo "❌ Échec de la création de l'environnement virtuel."
        read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
        exit 1
    fi
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo "✅ Environnement virtuel prêt"

# --- Dépendances ---
if ! python3 -c "import ccxt, dotenv" >/dev/null 2>&1; then
    echo "⏳ Installation des dépendances (peut prendre 1 à 2 minutes)..."
    pip install --quiet --upgrade pip
    if ! pip install --quiet -r requirements.txt; then
        echo "❌ Échec de l'installation des dépendances."
        read -n 1 -s -r -p "Appuyez sur une touche pour fermer..."
        exit 1
    fi
fi
echo "✅ Dépendances installées"

# --- Test des clés API ---
python3 test_api.py

echo ""
echo "==================================================="
echo " Copiez le résultat ci-dessus et envoyez-le à Claude."
echo " (Aucune clé n'est affichée, c'est sans risque.)"
echo "==================================================="
echo ""
read -n 1 -s -r -p "Appuyez sur une touche pour fermer cette fenêtre..."
echo ""
