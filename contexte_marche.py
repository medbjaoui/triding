#!/usr/bin/env python3
"""
Contexte de marché et PROBABILITÉS HISTORIQUES.

Ne prédit rien. Répond à une seule question, honnêtement :
« Quand le marché a déjà été dans cet état, que s'est-il passé ensuite,
  et à quelle fréquence ? »

Compare toujours la probabilité CONDITIONNELLE (dans cet état) à la probabilité
DE BASE (tous les jours confondus). Si les deux sont identiques, le signal ne
vaut rien — et le script le dit.

    python3 contexte_marche.py            # BTC
    python3 contexte_marche.py --coin ETH
"""
import argparse, math, sys
try:
    import ccxt
except ImportError:
    print("Lancez d'abord LANCER_TEST.command"); sys.exit(1)

HORIZONS = [7, 30, 90]   # jours

def sma(v, p):
    out, s = [None]*len(v), 0.0
    for i, x in enumerate(v):
        s += x
        if i >= p: s -= v[i-p]
        if i >= p-1: out[i] = s/p
    return out

def rsi_serie(v, p=14):
    out = [None]*len(v)
    if len(v) <= p: return out
    g = [max(v[i]-v[i-1], 0.0) for i in range(1, len(v))]
    l = [max(v[i-1]-v[i], 0.0) for i in range(1, len(v))]
    ag, al = sum(g[:p])/p, sum(l[:p])/p
    out[p] = 100.0 if al == 0 else 100-100/(1+ag/al)
    for i in range(p, len(g)):
        ag = (ag*(p-1)+g[i])/p; al = (al*(p-1)+l[i])/p
        out[i+1] = 100.0 if al == 0 else 100-100/(1+ag/al)
    return out

def volatilite(v, p=30):
    out = [None]*len(v)
    for i in range(p, len(v)):
        r = [math.log(v[j]/v[j-1]) for j in range(i-p+1, i+1)]
        m = sum(r)/len(r)
        out[i] = math.sqrt(sum((x-m)**2 for x in r)/len(r))*math.sqrt(365)*100
    return out

def etat(i, closes, s50, s200, rs, vol, seuil_vol):
    if None in (s50[i], s200[i], rs[i], vol[i]): return None
    return {
        "sur_sma50":  closes[i] > s50[i],
        "sur_sma200": closes[i] > s200[i],
        "rsi_zone":   ("survente" if rs[i] < 30 else "bas" if rs[i] < 50
                       else "haut" if rs[i] < 70 else "surachat"),
        "vol_zone":   ("faible" if vol[i] < seuil_vol[0] else
                       "élevée" if vol[i] > seuil_vol[1] else "normale"),
    }

def intervalle(k, n):
    """Intervalle de confiance 95 % (Wilson) pour une proportion."""
    if n == 0: return (0.0, 0.0)
    p, z = k/n, 1.96
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    e = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (max(0, (c-e))*100, min(1, (c+e))*100)

def charger(ex, sym, jours=2000):
    ms = ex.parse_timeframe("1d")*1000
    depuis = ex.milliseconds() - jours*86400*1000
    tout, vu = [], set()
    while True:
        lot = ex.fetch_ohlcv(sym, "1d", since=depuis, limit=1000)
        if not lot: break
        for c in lot:
            if c[0] not in vu: vu.add(c[0]); tout.append(c)
        if len(lot) < 1000: break
        depuis = lot[-1][0]+ms
    return sorted(tout, key=lambda c: c[0])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coin", default="BTC")
    a = ap.parse_args()
    sym = f"{a.coin.upper()}/USDT"

    ex = ccxt.binance({"enableRateLimit": True})
    print(f"\nChargement de l'historique {sym}...", end="", flush=True)
    b = charger(ex, sym)
    closes = [x[4] for x in b]
    print(f" {len(closes)} jours\n")
    if len(closes) < 400:
        print("Historique trop court pour des statistiques fiables."); return

    s50, s200, rs = sma(closes, 50), sma(closes, 200), rsi_serie(closes)
    vol = volatilite(closes)
    vv = sorted(x for x in vol if x is not None)
    seuil_vol = (vv[len(vv)//3], vv[2*len(vv)//3])

    ici = etat(len(closes)-1, closes, s50, s200, rs, vol, seuil_vol)
    if not ici:
        print("Données insuffisantes."); return

    print("="*74)
    print(f"ÉTAT ACTUEL DU MARCHÉ — {sym}")
    print("="*74)
    print(f"  Prix                {closes[-1]:,.2f} USDT".replace(",", " "))
    print(f"  Tendance moyen terme{'  au-dessus' if ici['sur_sma50'] else '  en dessous'} de la moyenne 50 j")
    print(f"  Tendance long terme {'  au-dessus' if ici['sur_sma200'] else '  en dessous'} de la moyenne 200 j")
    print(f"  RSI                 {rs[-1]:.1f}  ({ici['rsi_zone']})")
    print(f"  Volatilité          {vol[-1]:.0f}% annualisée  ({ici['vol_zone']})")

    # --- probabilité de base, tous jours confondus ---
    print(f"\n{'='*74}")
    print("PROBABILITÉS — conditionnelle vs. probabilité de base")
    print("="*74)
    print("\nLa colonne qui compte est le DÉCALAGE : si la probabilité dans cet état")
    print("est identique à la probabilité de base, l'information ne sert à rien.\n")

    for niveau, cle in [("Tendance seule", ("sur_sma50", "sur_sma200")),
                        ("Tendance + RSI", ("sur_sma50", "sur_sma200", "rsi_zone")),
                        ("Tendance + RSI + volatilité",
                         ("sur_sma50", "sur_sma200", "rsi_zone", "vol_zone"))]:
        print(f"\n  ── {niveau} " + "─"*(60-len(niveau)))
        print(f"  {'Horizon':<10}{'Cas similaires':>16}{'Hausse':>10}"
              f"{'IC 95%':>18}{'Base':>9}{'Décalage':>11}")
        for h in HORIZONS:
            corr = [i for i in range(len(closes)-h)
                    if (e := etat(i, closes, s50, s200, rs, vol, seuil_vol))
                    and all(e[k] == ici[k] for k in cle)]
            tous = [i for i in range(len(closes)-h)
                    if etat(i, closes, s50, s200, rs, vol, seuil_vol)]
            if not tous: continue
            base = sum(1 for i in tous if closes[i+h] > closes[i])/len(tous)*100
            if len(corr) < 10:
                print(f"  {h:>3} jours {len(corr):>15}   échantillon trop petit "
                      f"— non exploitable")
                continue
            k = sum(1 for i in corr if closes[i+h] > closes[i])
            p = k/len(corr)*100
            lo, hi = intervalle(k, len(corr))
            print(f"  {h:>3} jours {len(corr):>15}{p:>9.0f}%"
                  f"{f'[{lo:.0f}-{hi:.0f}%]':>18}{base:>8.0f}%{p-base:>+10.0f}")

    print(f"\n{'='*74}")
    print("COMMENT LIRE CE TABLEAU")
    print("="*74)
    print("""
  • « Cas similaires » = nombre de fois où le marché a été dans cet état.
    Sous 30 cas, une différence de 10 points n'est probablement que du bruit.

  • « IC 95% » = fourchette réaliste. Si elle contient la probabilité de base,
    le décalage observé n'est PAS statistiquement significatif.

  • Un décalage de +5 points sur 40 cas ne se distingue pas du hasard.
    Il faut un gros décalage OU un très gros échantillon.

  • Plus on ajoute de conditions, plus l'échantillon rétrécit et moins le
    résultat est fiable. C'est pour ça que les trois niveaux sont affichés.

  ⚠️  Ce sont des FRÉQUENCES PASSÉES, pas des prédictions. Le marché n'a
     aucune obligation de répéter son histoire, et la crypto a peu d'années
     de recul — un seul grand cycle peut dominer toutes ces statistiques.
""")

if __name__ == "__main__":
    main()
