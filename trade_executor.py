#!/usr/bin/env python3
"""Paper-only portfolio engine. It never signs, broadcasts, or moves funds."""
import json
import os
import tempfile
from datetime import datetime, timezone
from common import get_logger

log = get_logger("trade_executor")
PAPER_LOG_PATH = os.path.join(os.environ.get("PAPER_BOT_DATA_DIR", "/tmp/paper-bot-data"), "paper_trades.json")
STARTING_EQUITY_USD = 10.00
MAX_POSITION_USD = 1.50
MAX_OPEN_POSITIONS = 2
MAX_DEPLOYED_PCT = 30.0
RISK_PER_POSITION_USD = 0.15
DAILY_LOSS_LIMIT_USD = 0.30
MAX_CONSECUTIVE_LOSSES = 3
FEE_PCT_PER_SIDE = 0.25
SLIPPAGE_PCT_PER_SIDE = 0.50


os.makedirs(os.path.dirname(PAPER_LOG_PATH), exist_ok=True)


def default_state():
    return {
        "starting_equity_usd": STARTING_EQUITY_USD,
        "cash_usd": STARTING_EQUITY_USD,
        "open_positions": [],
        "closed_trades": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "consecutive_losses": 0,
        "paused_date": None,
    }


def load_paper_log():
    if not os.path.exists(PAPER_LOG_PATH):
        return default_state()
    with open(PAPER_LOG_PATH) as f:
        data = json.load(f)
    # Backward compatibility with the old ledger is intentionally limited.
    for k, v in default_state().items():
        data.setdefault(k, v)
    return data


def save_paper_log(data):
    directory = os.path.dirname(os.path.abspath(PAPER_LOG_PATH)) or "."
    fd, tmp = tempfile.mkstemp(prefix="paper_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PAPER_LOG_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def closed_today(data):
    today = datetime.now(timezone.utc).date()
    return [t for t in data["closed_trades"] if datetime.fromisoformat(t["exit_time"]).date() == today]


def realized_pnl_today(data):
    return sum(float(t.get("pnl_usd", 0)) for t in closed_today(data))


def equity(data):
    open_value = sum(float(p.get("notional_usd", 0)) for p in data["open_positions"])
    unrealized = sum(float(p.get("unrealized_pnl_usd", 0)) for p in data["open_positions"])
    return float(data["cash_usd"]) + open_value + unrealized


def trading_paused(data):
    today = datetime.now(timezone.utc).date().isoformat()
    if realized_pnl_today(data) <= -DAILY_LOSS_LIMIT_USD:
        return True, "daily loss limit"
    if data.get("paused_date") == today:
        return True, "three consecutive losses"
    return False, ""


def position_size(data):
    eq = equity(data)
    deployed = sum(float(p["notional_usd"]) for p in data["open_positions"])
    remaining_deploy = max(0.0, eq * MAX_DEPLOYED_PCT / 100 - deployed)
    return max(0.0, min(MAX_POSITION_USD, eq * 0.15, remaining_deploy))


def paper_trade(candidate, data=None):
    data = data or load_paper_log()
    paused, reason = trading_paused(data)
    if paused:
        log.info(f"Skipping entries: {reason}")
        return None
    if len(data["open_positions"]) >= MAX_OPEN_POSITIONS:
        return None
    size = position_size(data)
    if size <= 0 or data["cash_usd"] < size:
        return None

    price = float(candidate["priceUsd"])
    entry_fill = price * (1 + SLIPPAGE_PCT_PER_SIDE / 100)
    tokens = size * (1 - FEE_PCT_PER_SIDE / 100) / entry_fill
    now = datetime.now(timezone.utc).isoformat()
    position = {
        "symbol": candidate.get("baseToken", {}).get("symbol"),
        "mint": candidate.get("baseToken", {}).get("address"),
        "pair_address": candidate.get("pairAddress"),
        "pair_url": candidate.get("url"),
        "entry_time": now,
        "entry_market_price_usd": price,
        "entry_fill_price_usd": entry_fill,
        "notional_usd": round(size, 4),
        "tokens": tokens,
        "peak_price_usd": price,
        "unrealized_pnl_usd": 0.0,
        "risk_budget_usd": RISK_PER_POSITION_USD,
    }
    data["cash_usd"] = round(data["cash_usd"] - size, 6)
    data["open_positions"].append(position)
    save_paper_log(data)
    log.info(f"[paper] opened {position['symbol']} for ${size:.2f} at ${price:.8g}")
    return position


def execute_candidates(candidates):
    data = load_paper_log()
    for candidate in candidates:
        if len(data["open_positions"]) >= MAX_OPEN_POSITIONS:
            break
        if candidate.get("baseToken", {}).get("address") in {p.get("mint") for p in data["open_positions"]}:
            continue
        paper_trade(candidate, data)
    return data


if __name__ == "__main__":
    from token_screener import discover_candidates
    execute_candidates(discover_candidates())
