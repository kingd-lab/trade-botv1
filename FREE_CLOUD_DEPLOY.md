# Free-cloud deployment

This version uses **GitHub Actions + Streamlit Community Cloud** instead of a paid persistent disk.

- GitHub Actions runs one paper-simulation cycle every 5 minutes and commits `data/` state back to the repository.
- Streamlit Community Cloud hosts the read-only dashboard for phone access.
- No wallet, signing, transaction broadcast, or real-money execution is included.
- The GitHub repository should contain only paper-simulation data and code. Never put API secrets/private keys in it.

## GitHub
1. Create a GitHub repository. Public is simplest for the dashboard because the dashboard reads the raw state files without authentication.
2. Upload all project files, including `.github/workflows/paper-bot.yml` and `data/.gitkeep`.
3. In **Settings → Actions → General**, make sure Actions are allowed.
4. In **Settings → Actions → General → Workflow permissions**, select **Read and write permissions** if the repository UI offers that setting. The workflow also requests `contents: write`.
5. Open **Actions → Paper Bot Cycle → Run workflow** once to test it.
6. After it succeeds, scheduled runs should occur about every 5 minutes. GitHub may delay scheduled workflows during busy periods.

## Streamlit Community Cloud
1. Deploy `dashboard.py` from the GitHub repository.
2. In the app settings, add a secret/environment variable named `GITHUB_RAW_BASE`.
3. Its value should be the raw GitHub directory URL ending in `/data`, for example:
   `https://raw.githubusercontent.com/YOUR_USERNAME/paper-bot-v3/main/data`
4. Open the Streamlit app URL from your phone.

The dashboard reads the latest `paper_trades.json` and `circuit_state.json` directly from GitHub.
