# Paper Bot v3 — Free Cloud Edition

Paper-only Solana market discovery/simulation dashboard.

## Architecture

GitHub Actions (scheduled paper cycles) → commits state → GitHub repository → Streamlit Community Cloud dashboard → phone.

This avoids a paid persistent server disk. GitHub Actions scheduling can be delayed, and Streamlit Community Cloud may sleep when idle, so this is not a guaranteed real-time service.
