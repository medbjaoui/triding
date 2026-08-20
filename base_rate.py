#!/usr/bin/env python3
"""
Mesure empirique : à quelle fréquence un actif gagne-t-il +50 % en 4 heures ?
Balaye l'historique réel de Binance et compte. Lecture seule, aucun ordre.
"""
import sys
try:
    import ccxt
except ImportError:
    print("Lancez d'abord LANCER_TEST.command"); sys.exit(1)

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "PEPE", "BONK",
         "SHIB", "AVAX", "LINK", "ADA"]
JOURS = 365
SEUILS = [50, 20, 10, 5]

def charger(ex, sym, jours):
    ms = ex.parse_timeframe("1h") * 1000
    depuis = ex.milliseconds() - jours * 86400 * 1000
    tout, vu = [], set()
    while True:
        lot = ex.fetch_ohlcv(sym, "1h", since=depuis, limit=1000)
        if not lot: break
        for c in lot:
            if c[0] not in vu: vu.add(c[0]); tout.append(c)
        if len(lot) < 1000: break
        depuis = lot[-1][0] + ms
    return sorted(tout, key=lambda c: c[0])

def main():
    ex = ccxt.binance({"enableRateLimit": True})
    print(f"\n{'='*74}")
    print("À QUELLE FRÉQUENCE UN ACTIF FAIT-IL +50 % EN 4 HEURES ?")
    print(f"{'='*74}")
    print(f"Fenêtres glissantes de 4 h, {JOURS} jours d'historique réel Binance\n")

    total = 0
    atteints = {s: 0 for s in SEUILS}
    record = ("", 0.0)
    pires = {s: [] for s in SEUILS}

    for c in COINS:
        sym = f"{c}/USDT"
        try:
            print(f"  {sym:<12}", end="", flush=True)
            b = charger(ex, sym, JOURS)
        except Exception as e:
            print(f"erreur ({type(e).__name__})"); continue
        if len(b) < 100:
            print("historique insuffisant"); continue
        closes = [x[4] for x in b]
        n_local = {s: 0 for s in SEUILS}
        for i in range(4, len(closes)):
            r = (closes[i] / closes[i-4] - 1) * 100
            total += 1
            if r > record[1]: record = (sym, r)
            for s in SEUILS:
                if r >= s:
                    atteints[s] += 1; n_local[s] += 1
        print(f"{len(closes):>6} fenêtres   +50% : {n_local[50]:>4}   "
              f"+20% : {n_local[20]:>4}   +10% : {n_local[10]:>5}")

    print(f"\n{'='*74}")
    print(f"RÉSULTAT — {total:,} fenêtres de 4 h analysées".replace(",", " "))
    print(f"{'='*74}\n")
    print(f"{'Gain en 4h':<14}{'Occurrences':>14}{'Fréquence':>14}{'Soit environ':>22}")
    print("-" * 74)
    for s in SEUILS:
        n = atteints[s]
        f = n / total * 100 if total else 0
        if f > 0:
            sur = f"1 fenêtre sur {int(100/f):,}".replace(",", " ")
        else:
            sur = "jamais observé"
        print(f"  +{s}%{'':<8}{n:>13,}{f:>13.3f}%{sur:>22}".replace(",", " "))
    print("-" * 74)
    print(f"\nMeilleure fenêtre observée : {record[0]} {record[1]:+.1f}%")

    f50 = atteints[50] / total * 100 if total else 0
    print(f"\n{'='*74}")
    print("CE QUE ÇA SIGNIFIE")
    print(f"{'='*74}")
    if f50 == 0:
        print("\nAucune fenêtre de 4 h n'a produit +50 % sur l'ensemble des coins")
        print("et de la période analysée. Le pari n'est pas risqué : il est perdu")
        print("d'avance sur cet horizon.")
    else:
        print(f"\nUne fenêtre sur {int(100/f50)} a produit +50 %.")
        print("MAIS : pour en profiter, il aurait fallu choisir CETTE fenêtre-là")
        print("À L'AVANCE, sur le bon coin. Après coup, on les voit toutes.")
        print("Avant coup, la probabilité de tomber dessus est celle affichée.")
    print("\nEt sur toutes les autres fenêtres — l'écrasante majorité — le capital")
    print("engagé sur ce pari subit le mouvement inverse.\n")

if __name__ == "__main__":
    main()
