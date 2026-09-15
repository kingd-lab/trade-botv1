# Cloud deployment guide

## Recommended architecture

Use one cloud web service with:

- `runner.py` as the continuous paper worker
- `dashboard.py` as the public Streamlit UI
- `/data` as persistent storage for `paper_trades.json`, `circuit_state.json`, and logs

This avoids the old v2 problem where a cloud dashboard could not see the bot's local ledger.

## Render

The included `render.yaml` and `Dockerfile` are configured for Render.

### Repository

Push the project folder to GitHub. Do not commit `.env`, API keys, wallet credentials, `paper_trades.json`, or `circuit_state.json`.

### Deploy

Create a Render Blueprint from the repository, or create a Docker web service and use the included Dockerfile. The Blueprint uses a 1 GB persistent disk mounted at `/data`.

### After deployment

Render gives the web service a public HTTPS URL. Open that URL in Chrome on your phone.

### Persistence

The bot stores its state under `/data`. This is important because a normal cloud service filesystem may be reset on deploy/restart. Render persistent disks preserve filesystem changes under their mount path.

### Secrets

If an API key is needed, add it in the cloud provider's environment/secrets settings. Do not put secrets in source code or `render.yaml`.

## Cost note

The included Render Blueprint uses the `starter` plan because Render documents persistent disks as a feature for paid services. Check the provider's current pricing before deploying.

## Safety

This package is deliberately paper-only. The cloud setup does not sign, broadcast, or move cryptocurrency.
