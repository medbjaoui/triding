#!/usr/bin/env python3
"""
Comparateur de coins — teste LA MÊME stratégie que le bot sur l'historique réel
de plusieurs cryptos, et les classe par performance.

    python3 backtest.py              # 6 mois, liste par défaut
    python3 backtest.py --jours 365  # 1 an

Les indicateurs sont importés de bot.py : c'est exactement la même logique.
"""

import argparse
import sys

try:
    import ccxt
except ImportError:
    print("Dépendances manquantes. Double-cliquez d'abord sur LANCER_TEST.command")
    sys.exit(1)

from bot import (ema, rsi, EMA_FAST, EMA_SLOW, RSI_PERIOD, RSI_MAX_BUY,
                 STOP_LOSS_PCT, TAKE_PROFIT_PCT)

FRAIS_PCT = 0.1          # 0,1 % par ordre (taux Binance standard)
CAPITAL_DEPART = 16.0    # USDT

COINS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
         "LINK/USDT", "AVAX/USDT", "ADA/USDT", "DOGE/USDT", "PEPE/USDT"]


def rsi_serie(values, period):
    """Série RSI complète — identique, valeur par valeur, à bot.rsi() appelé
    successivement sur values[:i+1] (Wilder est récursif depuis une amorce fixe)."""
    out = [None] * len(values)
    if len(values) < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    out[period] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        out[i + 1] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def charger_historique(ex, symbole, timeframe="1h", jours=180):
    ms_bougie = ex.parse_timeframe(timeframe) * 1000
    depuis = ex.milliseconds() - jours * 86400 * 1000
    tout, vu = [], set()
    while True:
        lot = ex.fetch_ohlcv(symbole, timeframe, since=depuis, limit=1000)
        if not lot:
            break
        for c in lot:
            if c[0] not in vu:
                vu.add(c[0]); tout.append(c)
        if len(lot) < 1000:
            break
        depuis = lot[-1][0] + ms_bougie
        if len(tout) > jours * 24 + 200:
            break
    return sorted(tout, key=lambda c: c[0])


def backtester(bougies):
    """Rejoue la stratégie du bot. Aucun lookahead : les signaux de la bougie i
    proviennent de la bougie i-1 (déjà clôturée), l'exécution se fait à l'ouverture
    de la bougie i. Stop-loss et take-profit sont testés sur le bas/haut de bougie."""
    closes = [c[4] for c in bougies]
    ef = ema(closes, EMA_FAST)
    es = ema(closes, EMA_SLOW)
    rs = rsi_serie(closes, RSI_PERIOD)

    capital = CAPITAL_DEPART
    position = None          # {"qty":…, "entree":…}
    trades = []
    pic, drawdown_max = capital, 0.0
    depart = max(EMA_SLOW, RSI_PERIOD) + 2

    for i in range(depart, len(bougies)):
        _, o, haut, bas, cloture, _ = bougies[i]
        sig_ef, sig_es, sig_rs = ef[i - 1], es[i - 1], rs[i - 1]
        if sig_ef is None or sig_es is None or sig_rs is None:
            continue

        if position:
            entree = position["entree"]
            prix_sl = entree * (1 - STOP_LOSS_PCT / 100)
            prix_tp = entree * (1 + TAKE_PROFIT_PCT / 100)
            sortie, motif = None, None
            if bas <= prix_sl:                       # stop-loss prioritaire (prudent)
                sortie, motif = prix_sl, "stop-loss"
            elif haut >= prix_tp:
                sortie, motif = prix_tp, "take-profit"
            elif sig_ef < sig_es:
                sortie, motif = o, "retournement"

            if sortie:
                brut = position["qty"] * sortie
                capital = brut * (1 - FRAIS_PCT / 100)
                trades.append({"pnl_pct": (capital / position["capital_avant"] - 1) * 100,
                               "motif": motif})
                position = None
                pic = max(pic, capital)
                drawdown_max = max(drawdown_max, (pic - capital) / pic * 100)
        else:
            if sig_ef > sig_es and sig_rs < RSI_MAX_BUY:
                engage = capital * (1 - FRAIS_PCT / 100)
                position = {"qty": engage / o, "entree": o, "capital_avant": capital}

    if position:  # position encore ouverte à la fin : on la valorise au dernier prix
        capital = position["qty"] * closes[-1] * (1 - FRAIS_PCT / 100)

    gagnants = [t for t in trades if t["pnl_pct"] > 0]
    buy_hold = (closes[-1] / closes[depart] - 1) * 100
    return {
        "rendement_pct": (capital / CAPITAL_DEPART - 1) * 100,
        "final": capital,
        "trades": len(trades),
        "taux_reussite": (len(gagnants) / len(trades) * 100) if trades else 0.0,
        "drawdown_max": drawdown_max,
        "buy_hold_pct": buy_hold,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=180)
    ap.add_argument("--tf", default="1h", help="unité de temps : 1h, 4h, 1d")
    args = ap.parse_args()

    ex = ccxt.binance({"enableRateLimit": True})
    print(f"\n=== Comparaison de coins — stratégie EMA {EMA_FAST}/{EMA_SLOW} + RSI < "
          f"{RSI_MAX_BUY:.0f}, SL -{STOP_LOSS_PCT}% / TP +{TAKE_PROFIT_PCT}% ===")
    print(f"Période : {args.jours} derniers jours, bougies {args.tf}, "
          f"frais {FRAIS_PCT}%/ordre, capital {CAPITAL_DEPART} USDT\n")

    resultats = []
    for symbole in COINS:
        try:
            print(f"  Chargement {symbole}...", end="", flush=True)
            bougies = charger_historique(ex, symbole, timeframe=args.tf,
                                         jours=args.jours)
            if len(bougies) < EMA_SLOW * 3:
                print(" historique insuffisant, ignoré")
                continue
            r = backtester(bougies)
            r["coin"] = symbole.replace("/USDT", "")
            resultats.append(r)
            print(f" {len(bougies)} bougies → {r['rendement_pct']:+.1f}%")
        except Exception as e:
            print(f" erreur ({type(e).__name__}), ignoré")

    if not resultats:
        print("\nAucun résultat exploitable.")
        return

    resultats.sort(key=lambda r: r["rendement_pct"], reverse=True)
    print("\n" + "=" * 78)
    print(f"{'Coin':<7}{'Stratégie':>12}{'Achat+garde':>14}{'Trades':>9}"
          f"{'Réussite':>11}{'Perte max':>12}{'Final':>10}")
    print("=" * 78)
    for r in resultats:
        print(f"{r['coin']:<7}{r['rendement_pct']:>11.1f}%{r['buy_hold_pct']:>13.1f}%"
              f"{r['trades']:>9}{r['taux_reussite']:>10.0f}%"
              f"{r['drawdown_max']:>11.1f}%{r['final']:>9.2f}$")
    print("=" * 78)

    meilleur = resultats[0]
    print(f"\n→ Meilleur sur cette période : {meilleur['coin']} "
          f"({meilleur['rendement_pct']:+.1f}%)")
    print(f"  Pour l'utiliser : mettez  PAIR={meilleur['coin']}/USDT  dans .env, "
          "puis relancez le bot.")
    print("\n⚠️  Les performances passées ne préjugent pas des performances futures.")
    print("   Un backtest ignore le slippage et suppose une exécution parfaite.")
    print("   Une stratégie qui bat 'achat+garde' sur 6 mois peut perdre sur les 6 suivants.\n")


if __name__ == "__main__":
    main()
