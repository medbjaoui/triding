#!/usr/bin/env python3
"""
Vérification des clés API Binance — à lancer EN LOCAL sur votre Mac.

    cd ~/Documents/triding
    source venv/bin/activate
    python3 test_api.py

Ce script lit les clés depuis .env, vérifie la connexion, les permissions
et le solde. Il n'affiche JAMAIS vos clés et ne passe AUCUN ordre.
"""

import os
import sys
from pathlib import Path

try:
    import ccxt
    from dotenv import load_dotenv
except ImportError:
    print("Dépendances manquantes. Lancez :  pip3 install -r requirements.txt")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

KEY = os.getenv("BINANCE_API_KEY", "").strip()
SECRET = os.getenv("BINANCE_API_SECRET", "").strip()
PAIR = os.getenv("PAIR", "BTC/USDT")

OK, KO, WARN = "  ✅", "  ❌", "  ⚠️ "


def main():
    print("\n=== Vérification des clés API Binance ===\n")

    # 1. Présence des clés
    if not KEY or not SECRET:
        print(KO, "Clés absentes du fichier .env")
        print("     Copiez .env.example en .env et remplissez BINANCE_API_KEY "
              "et BINANCE_API_SECRET.")
        sys.exit(1)
    print(OK, f"Clés trouvées dans .env (clé se terminant par ...{KEY[-4:]})")

    ex = ccxt.binance({
        "apiKey": KEY, "secret": SECRET,
        "enableRateLimit": True, "options": {"defaultType": "spot"},
    })

    # 2. Connexion publique
    try:
        ticker = ex.fetch_ticker(PAIR)
        print(OK, f"Connexion à Binance établie — {PAIR} à {ticker['last']:,.2f} USDT")
    except Exception as e:
        print(KO, f"Impossible de joindre Binance : {e}")
        print("     Vérifiez votre connexion Internet ou un éventuel blocage régional.")
        sys.exit(1)

    # 3. Authentification + solde
    try:
        bal = ex.fetch_balance()
    except ccxt.AuthenticationError as e:
        print(KO, f"Clés refusées par Binance : {e}")
        print("     Clé/secret erronés, clé supprimée, ou restriction IP active.")
        sys.exit(1)
    except ccxt.PermissionDenied as e:
        print(KO, f"Permissions insuffisantes : {e}")
        sys.exit(1)
    except Exception as e:
        print(KO, f"Erreur d'authentification : {e}")
        sys.exit(1)

    print(OK, "Authentification réussie (clé et secret valides)")

    usdt = float(bal.get("USDT", {}).get("free", 0.0))
    print(OK, f"Solde disponible : {usdt:.2f} USDT")
    if usdt < 6:
        print(WARN, "Moins de 6 USDT : sous le minimum d'ordre Binance (~5 USDT "
                    "+ marge). Le bot ne pourra pas acheter.")

    autres = {a: v["free"] for a, v in bal.items()
              if isinstance(v, dict) and v.get("free", 0) and a != "USDT"}
    if autres:
        apercu = ", ".join(f"{a}: {q}" for a, q in list(autres.items())[:5])
        print(OK, f"Autres actifs détenus — {apercu}")

    # 4. Permissions de la clé (le point critique)
    restrictions = None
    for nom in ("sapiGetAccountApirestrictions", "sapiGetAccountApiRestrictions"):
        methode = getattr(ex, nom, None)
        if methode:
            try:
                restrictions = methode()
                break
            except Exception:
                continue

    print()
    if restrictions:
        retraits = restrictions.get("enableWithdrawals")
        spot = restrictions.get("enableSpotAndMarginTrading")
        futures = restrictions.get("enableFutures")
        ip_only = restrictions.get("ipRestrict")

        if retraits:
            print(KO, "RETRAITS ACTIVÉS SUR CETTE CLÉ — DANGER")
            print("     Désactivez immédiatement 'Enable Withdrawals' dans "
                  "Binance > API Management.")
            print("     Si la clé fuite, votre compte peut être vidé.")
        else:
            print(OK, "Retraits désactivés — bonne configuration")

        if spot:
            print(OK, "Trading Spot autorisé — le bot pourra passer des ordres")
        else:
            print(KO, "Trading Spot NON autorisé — activez 'Enable Spot & Margin "
                      "Trading' dans Binance > API Management")

        if futures:
            print(WARN, "Futures activés : inutile pour ce bot, et risqué "
                        "(liquidation). À désactiver de préférence.")

        print(OK if ip_only else WARN,
              "Clé restreinte à des IP de confiance" if ip_only
              else "Pas de restriction IP — acceptable si votre IP change souvent, "
                   "mais gardez la clé secrète")
    else:
        print(WARN, "Impossible de lire les permissions de la clé automatiquement.")
        print("     Vérifiez à la main dans Binance > API Management que "
              "'Enable Withdrawals' est bien DÉCOCHÉ.")

    # 5. Mode du bot
    dry = os.getenv("DRY_RUN", "true").lower() != "false"
    print()
    if dry:
        print(OK, "Bot en mode DRY-RUN : aucun ordre réel ne sera passé.")
        print("     Passez DRY_RUN=false dans .env quand vous voudrez trader "
              "pour de vrai.")
    else:
        print(WARN, "Bot en mode RÉEL : les ordres seront exécutés avec votre argent.")

    print("\n=== Vérification terminée — aucun ordre n'a été passé ===\n")


if __name__ == "__main__":
    main()
