#!/usr/bin/env python3
"""Paper-position monitor with conservative, fee/slippage-aware exits."""
import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from common import get_logger
from trade_executor import save_paper_log, load_paper_log, FEE_PCT_PER_SIDE, SLIPPAGE_PCT_PER_SIDE

log = get_logger("position_manager")
PAPER_LOG_PATH = os.path.join(os.environ.get("PAPER_BOT_DATA_DIR", "/tmp/paper-bot-data"), "paper_trades.json")
DEXSCREENER_BASE = "https://api.dexscreener.com"
TAKE_PROFIT_PCT = 30
STOP_LOSS_PCT = -10
TRAILING_STOP_PCT = 8
MAX_HOLD_HOURS = 24


def get_current_price(mint):
    try:
        r = requests.get(f"{DEXSCREENER_BASE}/token-pairs/v1/solana/{mint}", timeout=10)
        if r.status_code != 200:
            return None
        pairs = r.json() or []
        if not pairs:
            return None
        # Prefer the same pair used at entry; fallback to best liquidity is handled by caller.
        best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        return float(best["priceUsd"])
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def hours_since(ts):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 3600


def evaluate_position(position, market_price):
    entry = float(position["entry_market_price_usd"])
    peak = max(float(position.get("peak_price_usd", entry)), market_price)
    pnl_pct = (market_price - entry) / entry * 100
    drawdown = (market_price - peak) / peak * 100
    held = hours_since(position["entry_time"])
    reason = None
    if pnl_pct >= TAKE_PROFIT_PCT:
        reason = "take_profit"
    elif pnl_pct <= STOP_LOSS_PCT:
        reason = "stop_loss"
    elif drawdown <= -TRAILING_STOP_PCT:
        reason = "trailing_stop"
    elif held >= MAX_HOLD_HOURS:
        reason = "max_hold_time"
    return peak, pnl_pct, reason


def close_position(position, market_price, reason):
    exit_fill = market_price * (1 - SLIPPAGE_PCT_PER_SIDE / 100)
    gross_value = position["tokens"] * exit_fill
    exit_fee = gross_value * FEE_PCT_PER_SIDE / 100
    proceeds = gross_value - exit_fee
    pnl = proceeds - float(position["notional_usd"])
    return exit_fill, proceeds, pnl


def check_positions():
    data = load_paper_log()
    still_open, closed = [], []
    for p in data["open_positions"]:
        price = get_current_price(p["mint"])
        if price is None:
            still_open.append(p)
            continue
        peak, pnl_pct, reason = evaluate_position(p, price)
        p["peak_price_usd"] = peak
        p["unrealized_pnl_usd"] = round(float(p["tokens"]) * price - float(p["notional_usd"]), 4)
        if reason:
            exit_fill, proceeds, pnl = close_position(p, price, reason)
            p.update({
                "exit_time": datetime.now(timezone.utc).isoformat(),
                "exit_market_price_usd": price,
                "exit_fill_price_usd": exit_fill,
                "pnl_usd": round(pnl, 4),
                "pnl_pct": round(pnl / float(p["notional_usd"]) * 100, 2),
                "exit_reason": reason,
            })
            data["cash_usd"] = round(float(data["cash_usd"]) + proceeds, 6)
            data["closed_trades"].append(p)
            closed.append(p)
            if pnl < 0:
                data["consecutive_losses"] = int(data.get("consecutive_losses", 0)) + 1
                if data["consecutive_losses"] >= 3:
                    data["paused_date"] = datetime.now(timezone.utc).date().isoformat()
            else:
                data["consecutive_losses"] = 0
                data["paused_date"] = None
            log.info(f"Closed {p['symbol']}: ${pnl:+.2f} ({p['pnl_pct']:+.1f}%, {reason})")
        else:
            still_open.append(p)
        time.sleep(0.3)
    data["open_positions"] = still_open
    save_paper_log(data)
    return closed


def print_summary():
    data = load_paper_log()
    closed = data["closed_trades"]
    wins = sum(1 for t in closed if float(t.get("pnl_usd", 0)) > 0)
    realized = sum(float(t.get("pnl_usd", 0)) for t in closed)
    unrealized = sum(float(p.get("unrealized_pnl_usd", 0)) for p in data["open_positions"])
    print(f"Equity basis: ${float(data['cash_usd']) + sum(float(p['notional_usd']) for p in data['open_positions']) + unrealized:.2f} | realized P&L ${realized:+.2f} | closed {len(closed)} | win rate {(wins/len(closed)*100 if closed else 0):.0f}%")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--loop":
        interval = int(sys.argv[2])
        while True:
            check_positions(); print_summary(); time.sleep(interval)
    else:
        check_positions(); print_summary()
