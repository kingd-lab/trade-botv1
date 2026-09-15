# Paper Bot v3 — Free Cloud Mode

This package is a **paper-only** Solana market discovery/trading simulator. It never signs, broadcasts, or moves real funds.

## What the free mode does
- Runs the paper runner and read-only Streamlit dashboard in one Render web service.
- Uses Render's free plan.
- Stores temporary state under `/tmp/paper-bot-data`.
- Lets you open the dashboard from your phone while your computer is off.

## Important free-plan limitation
Render's free service filesystem is ephemeral and free services can spin down when idle. Therefore the paper ledger can reset after a restart, redeploy, or other instance replacement. The simulator is intentionally designed to fail safely by starting again at the configured virtual equity rather than pretending old state still exists.

For permanent history, use a paid persistent disk or add an external database later.

## Deploy
1. Create a private GitHub repository.
2. Upload the files in this folder.
3. In Render choose **New → Web Service** and connect the GitHub repo.
4. Runtime: **Docker**.
5. Plan: **Free**.
6. Create the service. The included `render.yaml` is already configured for the free plan.
7. Open the generated `onrender.com` URL on your phone.

No wallet, private key, or real-money execution is included.
