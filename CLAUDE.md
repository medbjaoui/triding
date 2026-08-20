# Instructions Claude — projet « triding »

Bot de trading automatisé Binance Spot appartenant à Mohamed. Répondre en français.

## Contexte

- Capital de départ : ~12 USDT, argent réel. Objectif : apprentissage et validation d'un système automatisé, pas de promesse de rendement.
- Stratégie : suivi de tendance EMA 20/50 (bougies 1h) + filtre RSI 14, une seule paire (BTC/USDT), une seule position, stop-loss −3 %, take-profit +5 %, sortie sur retournement EMA. Justification : ordre minimum Binance ~5 USDT et frais 0,2 % l'aller-retour interdisent grid/scalping/multi-paires.
- Le bot (`bot.py`) tourne sur le Mac de Mohamed. `DRY_RUN=true` par défaut.

## Fichiers

- `bot.py` — bot complet (indicateurs en Python pur, ccxt pour l'exchange).
- `.env` — clés API et paramètres. **Ne jamais lire ni afficher les valeurs des clés. Ne jamais copier `.env` vers le cloud.**
- `state.json` — position, trades, P&L cumulé. `status.json` — instantané pour supervision. `trades.log` — journal.

## Règles pour Claude

1. **Sécurité d'abord** : jamais de clés API dans le cloud, dans les logs ou dans les réponses. Les clés Binance ne doivent jamais avoir le droit de retrait.
2. **Aucun ordre réel sans demande explicite de Mohamed.** Ne jamais passer `DRY_RUN` à `false` de sa propre initiative.
3. Pour la supervision : lire `status.json` et les dernières lignes de `trades.log`, résumer position / P&L / tendance / anomalies (bot arrêté = `updated_at` vieux de plus d'une heure).
4. Toute modification de stratégie : expliquer le raisonnement, la tester en dry-run, et rappeler l'impact des frais (0,1 %/ordre) et du min notional (5 USDT).
5. Rappeler les risques quand pertinent, sans moraliser à chaque message.
6. Le capital est trop petit pour : grid trading, multi-paires, futures/levier (à déconseiller activement — risque de liquidation).

## Améliorations envisageables (backlog)

- Backtest de la stratégie sur données historiques (ccxt fetch_ohlcv).
- Trailing stop au lieu du take-profit fixe.
- Notifications (rapport Claude quotidien déjà en place).
