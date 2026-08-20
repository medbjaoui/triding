# Bot de trading Binance — projet « triding »

Bot de trading automatisé sur Binance Spot, conçu pour un micro-capital (~12 USDT), avec supervision quotidienne par Claude.

## ⚠️ À lire avant tout

- **Le trading crypto comporte un risque réel de perte totale.** N'investissez jamais plus que ce que vous pouvez perdre. Ce projet est avant tout un apprentissage : avec 12 $, les gains réalistes se comptent en centimes — l'objectif est de valider un système, pas de générer un revenu.
- Ceci n'est pas un conseil financier.
- Vérifiez la réglementation locale : en Tunisie, le statut des cryptomonnaies est restrictif/flou — renseignez-vous avant de trader en réel.
- Le bot démarre en **mode simulation (`DRY_RUN=true`)**. Laissez-le tourner quelques jours en simulation avant de passer en réel, même si le capital est petit.

## Stratégie choisie (et pourquoi)

**Suivi de tendance basse fréquence : croisement EMA 20/50 sur bougies 1h + filtre RSI 14.**

Contraintes d'un capital de 12 USDT sur Binance Spot :

- Ordre minimum ≈ 5 USDT → **une seule position à la fois** (~11,5 USDT), une seule paire (BTC/USDT, la plus liquide).
- Frais 0,1 % par ordre (0,2 % l'aller-retour) → le scalping et le grid trading sont perdants d'avance. Il faut **peu de trades, bien filtrés**.

Règles :

- **Achat** : EMA20 > EMA50 (tendance haussière confirmée sur bougie clôturée) ET RSI < 70 (pas de surchauffe), aucune position ouverte.
- **Vente** : stop-loss à −3 %, take-profit à +5 %, ou retournement de tendance (EMA20 repasse sous EMA50).
- Vérification toutes les 15 minutes ; les signaux sont calculés sur bougies clôturées pour éviter les faux signaux.

## Étape 1 — Créer les clés API Binance (sécurité !)

1. Binance → profil → **Account** → **API Management** → *Create API*.
2. Type « System generated », nommez-la (ex. `bot-triding`).
3. Permissions : cochez **uniquement** *Enable Reading* et *Enable Spot & Margin Trading*.
4. **Ne cochez JAMAIS *Enable Withdrawals*** — même piratée, la clé ne pourra pas vider votre compte vers l'extérieur.
5. Idéalement, restreignez la clé à l'IP de votre connexion (option *Restrict access to trusted IPs*). Attention : si votre IP change souvent (box résidentielle), la clé cessera de fonctionner — dans ce cas laissez sans restriction IP mais gardez la clé secrète.
6. Copiez la clé et le secret dans le fichier `.env` (le secret n'est montré qu'une fois).

## Étape 2 — Installation (dans le Terminal de votre Mac)

```bash
cd ~/Documents/triding
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# puis éditez .env pour ajouter vos clés
```

## Étape 3 — Lancement

```bash
source venv/bin/activate
python3 bot.py            # boucle continue (Mac allumé)
# ou
python3 bot.py --once     # une seule vérification (utilisable en cron)
```

Passage en réel : mettez `DRY_RUN=false` dans `.env` — seulement après quelques jours de simulation concluants.

Pour qu'il tourne en arrière-plan :

```bash
nohup python3 bot.py > /dev/null 2>&1 &
```

(Le bot s'arrête si le Mac s'éteint ou se met en veille — réglez la veille dans Réglages Système > Batterie si besoin.)

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `bot.py` | Le bot (stratégie + exécution) |
| `.env` | Vos clés et paramètres (jamais partagé) |
| `state.json` | Position ouverte, historique des trades, P&L cumulé |
| `status.json` | Instantané pour la supervision Claude (mis à jour à chaque cycle) |
| `trades.log` | Journal complet |
| `CLAUDE.md` | Instructions pour les sessions Claude sur ce projet |

## Supervision par Claude

Une tâche planifiée Claude lit chaque matin `status.json` et `trades.log` dans ce dossier (via l'app de bureau Claude) et envoie un rapport : position, P&L, signaux, anomalies. Le Mac doit avoir l'app Claude ouverte pour que la tâche accède au dossier.

Vous pouvez aussi, à tout moment, ouvrir une session Claude dans ce dossier et demander : « analyse les performances du bot » ou « ajuste la stratégie ».
