#!/usr/bin/env python3
"""Free-cloud, read-only Streamlit dashboard for the paper-only simulator.

It reads the latest state directly from GitHub so the dashboard does not need a
persistent server disk. Set GITHUB_RAW_BASE in Streamlit secrets/env to the raw
base URL of this repository, ending in /data.
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Paper Bot Free Cloud", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

DEFAULT_DATA = {"starting_equity_usd": 10, "cash_usd": 10, "open_positions": [], "closed_trades": []}


def load_json_url(url, default):
    try:
        r = requests.get(url, timeout=10, headers={"Cache-Control": "no-cache"})
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return default


def money(x):
    return f"${float(x):,.2f}"


def pct(x):
    return f"{float(x):+.2f}%"


def iso_date(ts):
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "—"


def raw_base():
    # Streamlit Community Cloud can expose this as an environment variable or secret.
    value = os.environ.get("GITHUB_RAW_BASE", "").strip().rstrip("/")
    try:
        value = st.secrets.get("GITHUB_RAW_BASE", value).strip().rstrip("/")
    except Exception:
        pass
    return value


st.title("📊 Paper Bot — Free Cloud")
st.caption("$10 virtual portfolio • paper simulation only • read-only")

base = raw_base()
if not base:
    st.error("GITHUB_RAW_BASE is not configured. Add it in the app's Streamlit secrets/environment settings.")
    st.stop()

if st.button("🔄 Refresh dashboard"):
    st.rerun()

# Add a cache-busting query so the dashboard sees newly committed GitHub state.
cache_buster = int(datetime.now(timezone.utc).timestamp() // 30)
ledger_url = f"{base}/paper_trades.json?cb={cache_buster}"
circuit_url = f"{base}/circuit_state.json?cb={cache_buster}"

data = load_json_url(ledger_url, DEFAULT_DATA)
closed = data.get("closed_trades", [])
open_pos = data.get("open_positions", [])
realized = sum(float(t.get("pnl_usd", 0)) for t in closed)
unrealized = sum(float(p.get("unrealized_pnl_usd", 0)) for p in open_pos)
deployed = sum(float(p.get("notional_usd", 0)) for p in open_pos)
equity = float(data.get("cash_usd", 0)) + deployed + unrealized
start = float(data.get("starting_equity_usd", 10))
total_return = (equity / start - 1) * 100 if start else 0
wins = sum(float(t.get("pnl_usd", 0)) > 0 for t in closed)
losses = sum(float(t.get("pnl_usd", 0)) < 0 for t in closed)
winrate = wins / len(closed) * 100 if closed else 0

circuit = load_json_url(circuit_url, {})
today = datetime.now(timezone.utc).date().isoformat()
paused = data.get("paused_date") == today
daily_realized = sum(float(t.get("pnl_usd", 0)) for t in closed if str(t.get("exit_time", ""))[:10] == today)

cols = st.columns(2)
cols[0].metric("Virtual Equity", money(equity), pct(total_return))
cols[1].metric("Cash", money(data.get("cash_usd", 0)), f"{deployed/start*100:.0f}% deployed" if start else "")
cols = st.columns(2)
cols[0].metric("Realized P&L", money(realized), pct(realized / start * 100 if start else 0))
cols[1].metric("Daily P&L", money(daily_realized), "Limit −$0.30")

st.divider()
status = "⏸️ PAUSED" if paused or circuit.get("tripped") else "🟢 RUNNING"
st.subheader(f"Status: {status}")
if circuit.get("tripped_reason"):
    st.warning(f"Circuit breaker: {circuit['tripped_reason']}")
if paused:
    st.warning("New entries are paused for today after the loss-streak rule.")

st.subheader(f"Open positions ({len(open_pos)}/2)")
if open_pos:
    rows = []
    for p in open_pos:
        entry = float(p.get("entry_market_price_usd", 0))
        peak = float(p.get("peak_price_usd", entry))
        u = float(p.get("unrealized_pnl_usd", 0))
        rows.append({"Token": p.get("symbol", "?"), "Size": money(p.get("notional_usd", 0)), "Entry": f"${entry:.8g}", "Peak": f"${peak:.8g}", "Unrealized": money(u), "Opened": iso_date(p.get("entry_time", ""))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions.")

st.subheader(f"Trade history ({len(closed)})")
if closed:
    rows = []
    for t in reversed(closed[-100:]):
        rows.append({"Token": t.get("symbol", "?"), "P&L": money(t.get("pnl_usd", 0)), "Return": pct(t.get("pnl_pct", 0)), "Exit": t.get("exit_reason", ""), "Closed": iso_date(t.get("exit_time", ""))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No closed trades yet.")

st.subheader("Performance")
st.json({
    "Closed trades": len(closed),
    "Wins": wins,
    "Losses": losses,
    "Win rate": f"{winrate:.1f}%",
    "Consecutive losses": data.get("consecutive_losses", 0),
    "Unrealized P&L": money(unrealized),
})

st.subheader("Strategy")
st.markdown("**Balanced paper configuration:** TP +30% • hard stop −10% • trailing stop 8% • max hold 24h • max 2 positions • max $1.50/position • daily loss limit −$0.30 • pause after 3 consecutive losses.")
st.caption(f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
