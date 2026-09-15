# Paper Bot v3 — cloud-ready setup

This package is **paper-only**. It never signs, broadcasts, or moves real funds.

## Local

```bash
pip install -r requirements.txt
PAPER_BOT_DATA_DIR=./data ./start.sh
```

The dashboard and paper worker run together. The ledger is stored in `./data`.

## Render deployment

The project includes `Dockerfile` and `render.yaml` for a Render web service.

1. Put this folder in a GitHub repository.
2. Create a Render Blueprint from that repository.
3. Keep the persistent disk mounted at `/data`.
4. Deploy the service.
5. Open the resulting HTTPS service URL on your phone.

The service starts both the paper worker and the Streamlit dashboard. The dashboard is read-only.

### Persistence

Cloud filesystems can be ephemeral. This package writes its ledger and circuit state under `PAPER_BOT_DATA_DIR`, defaulting to `/data` in the cloud. The included Render configuration attaches a persistent disk there.

### Environment variables

Optional:

- `PAPER_BOT_DATA_DIR=/data`
- `ALERT_WEBHOOK_URL=...`
- Any existing market-data API keys required by the backtester should be configured as cloud secrets/environment variables rather than committed to Git.

## Reset the virtual account

Stop the service and remove `paper_trades.json` from the persistent data directory, then restart. This resets the paper account to the configured $10 starting balance.

## Safety

This remains a simulation. Cloud hosting does not add wallet access, signing, transaction broadcasting, or real-money execution.
