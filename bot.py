#!/usr/bin/env python3
"""
Bot de trading Binance Spot — stratégie suivi de tendance (EMA 20/50 + RSI 14, bougies 1h).
Conçu pour un micro-capital (~12 USDT) : une seule paire, une seule position, basse fréquence.

Usage:
    python3 bot.py            # boucle continue (vérifie toutes les 15 min)
    python3 bot.py --once     # une seule vérification puis quitte (pour cron/launchd)

SÉCURITÉ : utilisez des clés API SANS droit de retrait. DRY_RUN=true par défaut.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import ccxt
    from dotenv import load_dotenv
except ImportError:
    print("Dépendances manquantes. Lancez :  pip3 install -r requirements.txt")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
STATUS_FILE = BASE_DIR / "status.json"
LOG_FILE = BASE_DIR / "trades.log"

load_dotenv(BASE_DIR / ".env")

# ----------------------------- Configuration -----------------------------
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
PAIR = os.getenv("PAIR", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "1h")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "15"))

EMA_FAST = int(os.getenv("EMA_FAST", "20"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "50"))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_MAX_BUY = float(os.getenv("RSI_MAX_BUY", "70"))   # pas d'achat en surchauffe
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "3.0"))    # -3 %
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "5.0"))  # +5 %
CAPITAL_FRACTION = float(os.getenv("CAPITAL_FRACTION", "0.98"))  # % du solde USDT engagé
MIN_NOTIONAL = 6.0  # marge au-dessus du minimum Binance (5 USDT)
MAX_LOSS_PCT = float(os.getenv("MAX_LOSS_PCT", "25.0"))  # coupe-circuit global


class ArretDefinitif(Exception):
    """Perte maximale atteinte : le bot se coupe et refuse de continuer."""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("bot")

# ----------------------------- Indicateurs -----------------------------

def ema(values, period):
    """EMA classique ; retourne la liste complète (None tant que < period)."""
    out = [None] * len(values)
    if len(values) < period:
        return out
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    k = 2 / (period + 1)
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(values, period=14):
    """RSI de Wilder ; retourne la dernière valeur ou None."""
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)

# ----------------------------- État -----------------------------

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"position": None, "trades": [], "realized_pnl_usdt": 0.0}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def write_status(state, price, ema_fast, ema_slow, rsi_val, usdt_free, note=""):
    """Fichier lu par la tâche de supervision Claude — toujours à jour."""
    pos = state.get("position")
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pair": PAIR,
        "dry_run": DRY_RUN,
        "price": price,
        "ema_fast": round(ema_fast, 2) if ema_fast else None,
        "ema_slow": round(ema_slow, 2) if ema_slow else None,
        "rsi": round(rsi_val, 1) if rsi_val else None,
        "trend": "haussière" if (ema_fast and ema_slow and ema_fast > ema_slow) else "baissière",
        "usdt_free": usdt_free,
        "position": pos,
        "unrealized_pnl_pct": (round((price / pos["entry_price"] - 1) * 100, 2)
                               if pos and price else None),
        "realized_pnl_usdt": round(state.get("realized_pnl_usdt", 0.0), 4),
        "trades_count": len(state.get("trades", [])),
        "note": note,
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def write_alert(message):
    """Marque une anomalie dans status.json (lue par la supervision Claude)."""
    status = {}
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            status = {}
    status["alert"] = message
    status["alert_at"] = datetime.now(timezone.utc).isoformat()
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

# ----------------------------- Exchange -----------------------------

def make_exchange():
    ex = ccxt.binance({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    return ex


def get_usdt_free(ex):
    if DRY_RUN and not API_KEY:
        return 12.0  # simulation sans clés
    bal = ex.fetch_balance()
    return float(bal.get("USDT", {}).get("free", 0.0))

# ----------------------------- Logique de trading -----------------------------

def check_once(ex):
    state = load_state()
    ohlcv = ex.fetch_ohlcv(PAIR, TIMEFRAME, limit=max(EMA_SLOW * 3, 150))
    # on ignore la bougie en cours (non clôturée) pour les signaux
    closes = [c[4] for c in ohlcv[:-1]]
    last_price = float(ohlcv[-1][4])

    ema_f = ema(closes, EMA_FAST)[-1]
    ema_s = ema(closes, EMA_SLOW)[-1]
    rsi_v = rsi(closes, RSI_PERIOD)
    if ema_f is None or ema_s is None or rsi_v is None:
        log.warning("Pas assez de données pour calculer les indicateurs.")
        return

    try:
        usdt_free = get_usdt_free(ex)
    except (ccxt.AuthenticationError, ccxt.PermissionDenied):
        raise  # remonté à la boucle principale (clé invalide / IP changée)
    except Exception as e:
        log.error(f"Impossible de lire le solde : {e}")
        usdt_free = None

    pos = state.get("position")
    note = ""

    # ---- coupe-circuit : perte maximale globale ----
    if state.get("halted"):
        raise ArretDefinitif(state.get("halt_reason", "Perte maximale atteinte."))

    if usdt_free is not None:
        if not state.get("capital_initial"):
            state["capital_initial"] = usdt_free + (pos["qty"] * last_price if pos else 0.0)
            save_state(state)
            log.info(f"Capital de référence enregistré : "
                     f"{state['capital_initial']:.2f} USDT")

        depart = state["capital_initial"]
        valeur = usdt_free + (pos["qty"] * last_price if pos else 0.0)
        seuil = depart * (1 - MAX_LOSS_PCT / 100)
        if valeur < seuil:
            motif = (f"COUPE-CIRCUIT : capital tombé à {valeur:.2f} USDT, sous le seuil "
                     f"de {seuil:.2f} USDT (-{MAX_LOSS_PCT:.0f}% du départ "
                     f"{depart:.2f} USDT).")
            log.critical(motif)
            if pos:
                log.critical("Liquidation de la position ouverte, puis arrêt.")
                sell(ex, state, pos, last_price, "COUPE-CIRCUIT perte maximale")
                state = load_state()
            state["halted"] = True
            state["halt_reason"] = motif
            save_state(state)
            write_alert(motif + " Bot arrêté — aucune reprise automatique.")
            raise ArretDefinitif(motif)

    if pos:  # ---- position ouverte : gérer la sortie ----
        entry = pos["entry_price"]
        change_pct = (last_price / entry - 1) * 100
        reason = None
        if change_pct <= -STOP_LOSS_PCT:
            reason = f"STOP-LOSS ({change_pct:+.2f}%)"
        elif change_pct >= TAKE_PROFIT_PCT:
            reason = f"TAKE-PROFIT ({change_pct:+.2f}%)"
        elif ema_f < ema_s:
            reason = f"Retournement de tendance EMA ({change_pct:+.2f}%)"

        if reason:
            sell(ex, state, pos, last_price, reason)
        else:
            note = f"Position tenue ({change_pct:+.2f}%)"
            log.info(f"{PAIR} {last_price:.2f} | {note} | RSI {rsi_v:.1f}")
    else:  # ---- pas de position : chercher une entrée ----
        if ema_f > ema_s and rsi_v < RSI_MAX_BUY:
            if usdt_free is not None and usdt_free * CAPITAL_FRACTION >= MIN_NOTIONAL:
                buy(ex, state, last_price, usdt_free * CAPITAL_FRACTION)
            else:
                note = f"Signal d'achat mais solde insuffisant ({usdt_free} USDT)"
                log.warning(note)
        else:
            note = (f"Pas de signal (tendance "
                    f"{'haussière' if ema_f > ema_s else 'baissière'}, RSI {rsi_v:.1f})")
            log.info(f"{PAIR} {last_price:.2f} | {note}")

    write_status(state, last_price, ema_f, ema_s, rsi_v, usdt_free, note)


def buy(ex, state, price, quote_amount):
    ts = datetime.now(timezone.utc).isoformat()
    if DRY_RUN:
        qty = quote_amount / price
        log.info(f"[DRY-RUN] ACHAT {PAIR} : {quote_amount:.2f} USDT @ ~{price:.2f}")
    else:
        order = ex.create_order(PAIR, "market", "buy", None, None,
                                {"quoteOrderQty": round(quote_amount, 2)})
        qty = float(order.get("filled") or order["amount"])
        price = float(order.get("average") or price)
        log.info(f"ACHAT EXÉCUTÉ {PAIR} : {qty:.8f} @ {price:.2f}")

    state["position"] = {"qty": qty, "entry_price": price, "entry_time": ts}
    state["trades"].append({"time": ts, "side": "buy", "price": price,
                            "qty": qty, "dry_run": DRY_RUN})
    save_state(state)


def sell(ex, state, pos, price, reason):
    ts = datetime.now(timezone.utc).isoformat()
    qty = pos["qty"]
    if DRY_RUN:
        log.info(f"[DRY-RUN] VENTE {PAIR} : {qty:.8f} @ ~{price:.2f} — {reason}")
    else:
        # vend tout le solde réel de l'actif (arrondi géré par ccxt)
        base = PAIR.split("/")[0]
        bal = ex.fetch_balance()
        qty = float(bal.get(base, {}).get("free", qty))
        qty = float(ex.amount_to_precision(PAIR, qty))
        order = ex.create_order(PAIR, "market", "sell", qty)
        price = float(order.get("average") or price)
        log.info(f"VENTE EXÉCUTÉE {PAIR} : {qty:.8f} @ {price:.2f} — {reason}")

    pnl = (price - pos["entry_price"]) * qty
    state["realized_pnl_usdt"] = state.get("realized_pnl_usdt", 0.0) + pnl
    state["position"] = None
    state["trades"].append({"time": ts, "side": "sell", "price": price, "qty": qty,
                            "pnl_usdt": round(pnl, 4), "reason": reason,
                            "dry_run": DRY_RUN})
    save_state(state)
    log.info(f"P&L du trade : {pnl:+.4f} USDT | P&L cumulé : "
             f"{state['realized_pnl_usdt']:+.4f} USDT")

# ----------------------------- Main -----------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true",
                        help="une seule vérification puis quitte")
    args = parser.parse_args()

    if not DRY_RUN and (not API_KEY or not API_SECRET):
        log.error("DRY_RUN=false mais clés API absentes du fichier .env — arrêt.")
        sys.exit(1)

    mode = "DRY-RUN (simulation)" if DRY_RUN else "RÉEL"
    log.info(f"Démarrage du bot — {PAIR} {TIMEFRAME} — mode {mode}")
    ex = make_exchange()

    echecs_auth = 0
    while True:
        try:
            check_once(ex)
            echecs_auth = 0
        except ArretDefinitif as e:
            log.critical("=" * 60)
            log.critical(f"BOT ARRÊTÉ DÉFINITIVEMENT — {e}")
            log.critical("Vos fonds restent sur votre compte Binance.")
            log.critical("Pour relancer : supprimez 'halted' dans state.json "
                         "APRÈS avoir revu la stratégie.")
            log.critical("=" * 60)
            sys.exit(1)
        except (ccxt.AuthenticationError, ccxt.PermissionDenied) as e:
            echecs_auth += 1
            msg = str(e)
            if "-2015" in msg or "IP" in msg:
                raison = ("CLÉ API REFUSÉE — probablement un changement d'adresse IP "
                          "(connexion 5G/mobile). Mettez à jour la restriction IP dans "
                          "Binance > API Management, ou retirez-la.")
            else:
                raison = ("CLÉ API REFUSÉE — clé/secret invalides, supprimés, "
                          "ou permissions insuffisantes.")
            log.critical(raison)
            log.critical(f"Détail : {msg}")
            state = load_state()
            if state.get("position"):
                log.critical("⚠️  UNE POSITION EST OUVERTE et le bot ne peut plus vendre. "
                             "Le stop-loss ne s'appliquera PAS. Intervenez manuellement "
                             "sur Binance si nécessaire.")
                write_alert(raison + " POSITION OUVERTE NON PROTÉGÉE.")
            else:
                write_alert(raison)
            if echecs_auth >= 3:
                log.critical("3 échecs d'authentification consécutifs — arrêt du bot.")
                sys.exit(1)
        except ccxt.NetworkError as e:
            log.warning(f"Erreur réseau (nouvelle tentative au prochain cycle) : {e}")
        except Exception as e:
            log.error(f"Erreur inattendue : {e}")
        if args.once:
            break
        time.sleep(CHECK_INTERVAL_MIN * 60)


if __name__ == "__main__":
    main()
