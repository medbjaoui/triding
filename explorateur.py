#!/usr/bin/env python3
"""
Explorateur de stratégies — cherche s'il existe une stratégie rentable,
avec VALIDATION HORS ÉCHANTILLON pour éviter le surapprentissage.

Méthode :
  1. L'historique est coupé en deux : période de CALIBRAGE (60 %) et période
     de VALIDATION (40 %, jamais vue pendant le calibrage).
  2. Toutes les stratégies sont testées sur le calibrage. On retient les meilleures.
  3. Ces meilleures sont ensuite jouées sur la validation.
  4. Si une stratégie gagne au calibrage mais perd en validation, c'est du
     surapprentissage : elle est rejetée.

    python3 explorateur.py                    # BTC ETH SOL BNB, 4h et 1d, 2 ans
    python3 explorateur.py --tf 1h,4h,1d --jours 1095
"""
import argparse, itertools, sys
try:
    import ccxt
except ImportError:
    print("Lancez d'abord LANCER_TEST.command"); sys.exit(1)

FRAIS = 0.1  # % par ordre

# ------------------------- indicateurs (avec cache) -------------------------
_cache = {}

def ema(vals, p):
    k = ("ema", id(vals), p)
    if k in _cache: return _cache[k]
    out = [None]*len(vals)
    if len(vals) >= p:
        out[p-1] = sum(vals[:p])/p
        c = 2/(p+1)
        for i in range(p, len(vals)):
            out[i] = vals[i]*c + out[i-1]*(1-c)
    _cache[k] = out
    return out

def sma(vals, p):
    k = ("sma", id(vals), p)
    if k in _cache: return _cache[k]
    out, s = [None]*len(vals), 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= p: s -= vals[i-p]
        if i >= p-1: out[i] = s/p
    _cache[k] = out
    return out

def rsi(vals, p):
    k = ("rsi", id(vals), p)
    if k in _cache: return _cache[k]
    out = [None]*len(vals)
    if len(vals) > p:
        g = [max(vals[i]-vals[i-1], 0.0) for i in range(1, len(vals))]
        l = [max(vals[i-1]-vals[i], 0.0) for i in range(1, len(vals))]
        ag, al = sum(g[:p])/p, sum(l[:p])/p
        out[p] = 100.0 if al == 0 else 100-100/(1+ag/al)
        for i in range(p, len(g)):
            ag = (ag*(p-1)+g[i])/p; al = (al*(p-1)+l[i])/p
            out[i+1] = 100.0 if al == 0 else 100-100/(1+ag/al)
    _cache[k] = out
    return out

def plus_haut(hauts, p):
    k = ("hh", id(hauts), p)
    if k in _cache: return _cache[k]
    out = [None]*len(hauts)
    for i in range(p-1, len(hauts)): out[i] = max(hauts[i-p+1:i+1])
    _cache[k] = out
    return out

def plus_bas(bas, p):
    k = ("ll", id(bas), p)
    if k in _cache: return _cache[k]
    out = [None]*len(bas)
    for i in range(p-1, len(bas)): out[i] = min(bas[i-p+1:i+1])
    _cache[k] = out
    return out

# ------------------------- génération des signaux -------------------------

def signaux(cfg, closes, hauts, bas):
    """Retourne (entrees, sorties) : listes de booléens, index = bougie clôturée."""
    n = len(closes)
    e, s = [False]*n, [False]*n
    f = cfg["famille"]

    if f == "ema":
        ef, es = ema(closes, cfg["rapide"]), ema(closes, cfg["lent"])
        rv = rsi(closes, 14) if cfg.get("rsi_max") else None
        for i in range(n):
            if ef[i] is None or es[i] is None: continue
            if rv is not None and rv[i] is None: continue
            haussier = ef[i] > es[i]
            e[i] = haussier and (rv is None or rv[i] < cfg["rsi_max"])
            s[i] = not haussier

    elif f == "sma":
        m = sma(closes, cfg["periode"])
        for i in range(n):
            if m[i] is None: continue
            e[i] = closes[i] > m[i]
            s[i] = closes[i] < m[i]

    elif f == "rsi_rev":
        rv = rsi(closes, cfg["periode"])
        tendance = sma(closes, cfg["filtre"]) if cfg.get("filtre") else None
        for i in range(n):
            if rv[i] is None: continue
            if tendance is not None and (tendance[i] is None or closes[i] < tendance[i]):
                continue
            e[i] = rv[i] < cfg["survente"]
            s[i] = rv[i] > cfg["surachat"]

    elif f == "donchian":
        hh, ll = plus_haut(hauts, cfg["entree_n"]), plus_bas(bas, cfg["sortie_n"])
        for i in range(1, n):
            if hh[i-1] is None or ll[i-1] is None: continue
            e[i] = closes[i] >= hh[i-1]
            s[i] = closes[i] <= ll[i-1]
    return e, s

# ------------------------- moteur de backtest -------------------------

def moteur(bougies, cfg):
    closes = [c[4] for c in bougies]
    hauts  = [c[2] for c in bougies]
    bas    = [c[3] for c in bougies]

    if cfg["famille"] == "achat_garde":
        depart = 60
        r = (closes[-1]/closes[depart]-1)*100
        return {"rendement": r, "trades": 1, "reussite": 100.0 if r > 0 else 0.0,
                "drawdown": 0.0}

    ent, sor = signaux(cfg, closes, hauts, bas)
    sl, tp, tr = cfg.get("sl"), cfg.get("tp"), cfg.get("trailing")

    capital, position, trades = 100.0, None, []
    pic_cap, dd_max = capital, 0.0
    debut = 210  # marge pour les indicateurs les plus lents

    for i in range(debut, len(bougies)):
        o, h, b = bougies[i][1], bougies[i][2], bougies[i][3]
        if position:
            entree = position["entree"]
            position["pic"] = max(position["pic"], h)
            sortie = None
            if sl and b <= entree*(1-sl/100):
                sortie = entree*(1-sl/100)
            elif tr and b <= position["pic"]*(1-tr/100):
                sortie = min(o, position["pic"]*(1-tr/100))
            elif tp and h >= entree*(1+tp/100):
                sortie = entree*(1+tp/100)
            elif sor[i-1]:
                sortie = o
            if sortie:
                avant = position["capital_avant"]
                capital = position["qty"]*sortie*(1-FRAIS/100)
                trades.append((capital/avant-1)*100)
                position = None
                pic_cap = max(pic_cap, capital)
                dd_max = max(dd_max, (pic_cap-capital)/pic_cap*100)
        elif ent[i-1]:
            engage = capital*(1-FRAIS/100)
            position = {"qty": engage/o, "entree": o, "pic": o, "capital_avant": capital}

    if position:
        capital = position["qty"]*closes[-1]*(1-FRAIS/100)
    gagnants = [t for t in trades if t > 0]
    return {"rendement": capital-100.0, "trades": len(trades),
            "reussite": len(gagnants)/len(trades)*100 if trades else 0.0,
            "drawdown": dd_max}

# ------------------------- grille de stratégies -------------------------

def grille():
    cfgs = [{"famille": "achat_garde", "nom": "Acheter et garder"}]
    sorties = [{"sl": None, "tp": None, "trailing": None},
               {"sl": 3, "tp": 5, "trailing": None},
               {"sl": 8, "tp": 15, "trailing": None},
               {"sl": None, "tp": None, "trailing": 5},
               {"sl": None, "tp": None, "trailing": 10},
               {"sl": 10, "tp": None, "trailing": 15}]
    for (r, l) in [(9, 21), (20, 50), (50, 200)]:
        for rmax in [None, 70]:
            for s in sorties:
                c = {"famille": "ema", "rapide": r, "lent": l, "rsi_max": rmax}
                c.update(s)
                c["nom"] = (f"EMA {r}/{l}" + (f" RSI<{rmax}" if rmax else "") +
                            etiquette(s))
                cfgs.append(c)
    for p in [50, 100, 200]:
        for s in sorties[:4]:
            c = {"famille": "sma", "periode": p}; c.update(s)
            c["nom"] = f"Prix > SMA {p}" + etiquette(s); cfgs.append(c)
    for (sv, sa) in [(30, 70), (25, 65), (20, 60)]:
        for filtre in [None, 200]:
            for s in sorties[:4]:
                c = {"famille": "rsi_rev", "periode": 14, "survente": sv,
                     "surachat": sa, "filtre": filtre}
                c.update(s)
                c["nom"] = (f"RSI {sv}/{sa}" + (" +SMA200" if filtre else "") +
                            etiquette(s)); cfgs.append(c)
    for (en, so) in [(20, 10), (55, 20), (20, 20)]:
        for s in sorties[:4]:
            c = {"famille": "donchian", "entree_n": en, "sortie_n": so}; c.update(s)
            c["nom"] = f"Cassure {en}/{so}" + etiquette(s); cfgs.append(c)
    return cfgs

def etiquette(s):
    if s.get("trailing"): return f" trail{s['trailing']}%"
    if s.get("sl") and s.get("tp"): return f" SL{s['sl']}/TP{s['tp']}"
    if s.get("sl"): return f" SL{s['sl']}"
    return " signal seul"

# ------------------------- chargement -------------------------

def charger(ex, sym, tf, jours):
    ms = ex.parse_timeframe(tf)*1000
    depuis = ex.milliseconds() - jours*86400*1000
    tout, vu = [], set()
    while True:
        lot = ex.fetch_ohlcv(sym, tf, since=depuis, limit=1000)
        if not lot: break
        for c in lot:
            if c[0] not in vu: vu.add(c[0]); tout.append(c)
        if len(lot) < 1000: break
        depuis = lot[-1][0]+ms
    return sorted(tout, key=lambda c: c[0])

# ------------------------- programme principal -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,ETH,SOL,BNB")
    ap.add_argument("--tf", default="4h,1d")
    ap.add_argument("--jours", type=int, default=730)
    a = ap.parse_args()

    ex = ccxt.binance({"enableRateLimit": True})
    cfgs = grille()
    print(f"\n{'='*80}")
    print("EXPLORATEUR DE STRATÉGIES — avec validation hors échantillon")
    print(f"{'='*80}")
    print(f"{len(cfgs)} stratégies × {len(a.coins.split(','))} coins × "
          f"{len(a.tf.split(','))} unités de temps, sur {a.jours} jours")
    print("Calibrage sur les 60 % les plus anciens, validation sur les 40 % récents.\n")

    survivants, total_teste = [], 0
    for sym in [f"{c}/USDT" for c in a.coins.split(",")]:
        for tf in a.tf.split(","):
            try:
                print(f"  {sym} {tf} : chargement...", end="", flush=True)
                b = charger(ex, sym, tf, a.jours)
            except Exception as e:
                print(f" erreur ({type(e).__name__})"); continue
            if len(b) < 500:
                print(f" seulement {len(b)} bougies, ignoré"); continue
            coupe = int(len(b)*0.6)
            cal, val = b[:coupe], b[coupe-210:]  # recouvrement pour amorcer les indicateurs
            _cache.clear()

            res_cal = []
            for c in cfgs:
                if c["famille"] == "achat_garde": continue
                r = moteur(cal, c)
                if r["trades"] >= 5: res_cal.append((r["rendement"], c))
                total_teste += 1
            if not res_cal:
                print(" aucune stratégie exploitable"); continue
            res_cal.sort(key=lambda x: x[0], reverse=True)

            _cache.clear()
            ref_val = moteur(val, {"famille": "achat_garde"})["rendement"]
            print(f" {len(b)} bougies (achat+garde en validation : {ref_val:+.1f}%)")

            for rend_cal, c in res_cal[:5]:
                _cache.clear()
                rv = moteur(val, c)
                bat = rv["rendement"] > ref_val
                print(f"      {c['nom']:<34} calibrage {rend_cal:+7.1f}%  "
                      f"validation {rv['rendement']:+7.1f}%  "
                      f"{'✅ bat achat+garde' if bat else '❌'}")
                if bat and rv["rendement"] > 0:
                    survivants.append((sym, tf, c["nom"], rend_cal,
                                       rv["rendement"], ref_val, rv["trades"]))

    print(f"\n{'='*80}")
    print("VERDICT")
    print(f"{'='*80}")
    print(f"{total_teste} combinaisons testées au total.")
    if not survivants:
        print("\n❌ AUCUNE stratégie n'est rentable ET ne bat 'acheter et garder'")
        print("   sur la période de validation.")
        print("\n   Conclusion honnête : sur ces marchés et ces familles de stratégies,")
        print("   le trading automatisé par indicateurs simples n'a pas d'avantage")
        print("   exploitable après frais. Ce n'est pas un bug — c'est le résultat.")
    else:
        print(f"\n{len(survivants)} combinaison(s) rentable(s) ET battant achat+garde "
              "en validation :\n")
        for sym, tf, nom, rc, rv, ref, nt in sorted(survivants, key=lambda x: -x[4]):
            print(f"  {sym:<10}{tf:<4}{nom:<34} validation {rv:+7.1f}% "
                  f"(vs {ref:+.1f}%) — {nt} trades")
        attendu = total_teste*0.05
        print(f"\n⚠️  Sur {total_teste} tests, environ {attendu:.0f} peuvent ressortir")
        print("   gagnants par pur hasard. Ne retenez une stratégie que si elle")
        print("   apparaît sur PLUSIEURS coins et PLUSIEURS unités de temps —")
        print("   une seule ligne isolée n'est probablement que du bruit.")
    print()

if __name__ == "__main__":
    main()
