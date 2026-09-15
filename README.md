# Paper Bot v3 — Free Cloud

**Paper-only simulator. No real-money trading, signing, broadcasting, or fund movement.**

See `FREE_CLOUD.md` for free Render deployment.

# Paper Bot v3 — Cloud-ready

Paper-only Solana market-data simulator with a mobile Streamlit dashboard. **No wallet signing, transaction broadcasting, or movement of real funds is included.**

## Architecture

Cloud web service → persistent `/data` disk → paper runner + Streamlit dashboard.

The runner continuously discovers candidates, opens virtual positions, and checks exits. The dashboard reads the same persistent ledger and is read-only.

## Included

- $10 virtual starting equity
- Max $1.50 per position
- Max 2 simultaneous positions
- Max 30% deployed
- Daily loss limit $0.30
- Pause after 3 consecutive losses
- +30% TP / -10% hard stop / 8% trailing stop / 24h max hold
- Simulated fees and slippage
- Persistent cloud data directory via `PAPER_BOT_DATA_DIR`
- Docker deployment
- Render Blueprint (`render.yaml`)
- Mobile-friendly Streamlit dashboard

## Local

```bash
pip install -r requirements.txt
PAPER_BOT_DATA_DIR=./data ./start.sh
```

Then open the Streamlit URL shown by the terminal.

## Cloud deployment

The included `render.yaml` is prepared for a Render web service with a persistent disk mounted at `/data`. Render web services provide a public HTTPS URL. A persistent disk is required because Render's default filesystem is ephemeral.

1. Put this project in a GitHub repository.
2. In Render, create a Blueprint from the repository or create a Docker web service using the included `Dockerfile`.
3. Use the included `render.yaml` settings.
4. Keep the persistent disk mounted at `/data`.
5. Deploy.
6. Open the resulting `onrender.com` URL on your phone.

The bot and dashboard run together in the same service so they share the same persistent ledger.

## Optional environment variables

- `PAPER_BOT_DATA_DIR=/data`
- `ALERT_WEBHOOK_URL=...` (optional alert webhook)
- Any API keys required by the existing market-data/backtest code should be entered as cloud environment variables, never committed to Git.

## Important

This remains a simulation. Cloud hosting does not turn it into a real trading system. Do not add wallet keys or transaction-signing code to this package.
