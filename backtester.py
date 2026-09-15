#!/usr/bin/env python3
"""Paper strategy backtester using historical Birdeye price points.

It evaluates entry candidates already recorded by the paper bot. It does not claim
historical screener discovery and therefore measures exit/risk behavior, not full
historical discovery quality.
"""
import os, json, time, requests, math
from datetime import datetime, timezone, timedelta

PAPER_LOG_PATH = "paper_trades.json"
BIRDEYE_BASE = "https://public-api.birdeye.so"
API_KEY = os.environ.get("BIRDEYE_API_KEY")
REQUEST_DELAY_SEC = 1.1
LOOKFORWARD_HOURS = 24
CANDLE_INTERVAL = "15m"
FEE_PCT_PER_SIDE = 0.25
SLIPPAGE_PCT_PER_SIDE = 0.50
STARTING_EQUITY = 10.0
MAX_POSITION = 1.50
RULE_SWEEP = [
    (20, -8, 6),
    (30, -10, 8),
    (40, -12, 10),
]


def load_entries():
    try:
        with open(PAPER_LOG_PATH) as f: data = json.load(f)
    except FileNotFoundError: return []
    return data.get("open_positions", []) + data.get("closed_trades", [])


def get_prices(mint, start, end):
    if not API_KEY: raise RuntimeError("BIRDEYE_API_KEY is not set")
    params = {"address": mint, "address_type": "token", "type": CANDLE_INTERVAL, "time_from": int(start), "time_to": int(end)}
    headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": API_KEY}
    r = requests.get(f"{BIRDEYE_BASE}/defi/history_price", params=params, headers=headers, timeout=15)
    time.sleep(REQUEST_DELAY_SEC); r.raise_for_status()
    return r.json().get("data", {}).get("items", [])


def net_exit(entry_price, market_price, entry_notional):
    entry_fill = entry_price * (1 + SLIPPAGE_PCT_PER_SIDE/100)
    exit_fill = market_price * (1 - SLIPPAGE_PCT_PER_SIDE/100)
    tokens = entry_notional * (1 - FEE_PCT_PER_SIDE/100) / entry_fill
    proceeds = tokens * exit_fill * (1 - FEE_PCT_PER_SIDE/100)
    return proceeds - entry_notional


def simulate(prices, entry_price, notional, tp, sl, trail):
    peak = entry_price
    for p in prices:
        price = float(p["value"])
        peak = max(peak, price)
        pnl = (price-entry_price)/entry_price*100
        drawdown = (price-peak)/peak*100
        if pnl >= tp: return "take_profit", net_exit(entry_price, price, notional)
        if pnl <= sl: return "stop_loss", net_exit(entry_price, price, notional)
        if drawdown <= -trail: return "trailing_stop", net_exit(entry_price, price, notional)
    final = float(prices[-1]["value"]) if prices else entry_price
    return "time_exit", net_exit(entry_price, final, notional)


def metrics(values):
    if not values: return {}
    wins = [x for x in values if x > 0]; losses = [x for x in values if x < 0]
    gross_win = sum(wins); gross_loss = abs(sum(losses))
    equity = STARTING_EQUITY; peak = equity; max_dd = 0
    for x in values:
        equity += x; peak = max(peak, equity); max_dd = max(max_dd, (peak-equity)/peak*100)
    expectancy = sum(values)/len(values)
    pf = gross_win/gross_loss if gross_loss else math.inf
    return {"net": sum(values), "win_rate": len(wins)/len(values)*100, "max_dd_pct": max_dd, "expectancy": expectancy, "profit_factor": pf, "n": len(values)}


def run():
    entries = load_entries()
    if not entries: print("No paper entries found."); return
    if not API_KEY: print("Set BIRDEYE_API_KEY to run historical tests."); return
    totals = {f"TP{tp}/SL{sl}/TR{tr}": [] for tp,sl,tr in RULE_SWEEP}
    for entry in entries:
        if not entry.get("mint") or entry.get("entry_market_price_usd") is None: continue
        entered = datetime.fromisoformat(entry["entry_time"])
        try: prices = get_prices(entry["mint"], entered.timestamp(), (entered+timedelta(hours=LOOKFORWARD_HOURS)).timestamp())
        except (requests.RequestException, RuntimeError) as e:
            print(f"[skip] {entry.get('symbol')}: {e}"); continue
        if not prices: continue
        for tp,sl,tr in RULE_SWEEP:
            reason, pnl = simulate(prices, float(entry["entry_market_price_usd"]), min(MAX_POSITION, float(entry.get("notional_usd", MAX_POSITION))), tp, sl, tr)
            totals[f"TP{tp}/SL{sl}/TR{tr}"].append(pnl)
    print("\nSTRATEGY COMPARISON")
    for label, values in totals.items():
        m = metrics(values)
        if m: print(f"{label:<18} net ${m['net']:+.2f} | DD {m['max_dd_pct']:.1f}% | win {m['win_rate']:.0f}% | PF {m['profit_factor']:.2f} | n={m['n']}")

if __name__ == "__main__": run()
