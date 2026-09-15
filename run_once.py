#!/usr/bin/env python3
"""Run exactly one paper-simulation cycle for GitHub Actions."""
import traceback
from common import get_logger, CircuitBreaker, send_alert
import token_screener
import trade_executor
import position_manager

log = get_logger("run_once")
MAX_CONSECUTIVE_ERRORS = 5
MAX_CONSECUTIVE_LOSSES = 3


def main():
    breaker = CircuitBreaker(MAX_CONSECUTIVE_ERRORS, MAX_CONSECUTIVE_LOSSES)
    if breaker.is_tripped():
        log.warning("Circuit breaker already tripped: %s", breaker.state.get("tripped_reason"))
        return

    try:
        # Manage existing paper positions first so closed positions free capacity.
        for trade in position_manager.check_positions():
            pnl = float(trade.get("pnl_usd", 0))
            breaker.record_trade_result(pnl)
            if pnl <= -0.15:
                send_alert(f"Paper loss warning: {trade.get('symbol')} ${pnl:+.2f} ({trade.get('exit_reason')})")

        if breaker.is_tripped():
            return

        candidates = token_screener.discover_candidates()
        log.info("Found %d candidates.", len(candidates))
        trade_executor.execute_candidates(candidates)
        breaker.record_success()
    except Exception as exc:
        log.error("One-shot cycle failed: %s\n%s", exc, traceback.format_exc())
        breaker.record_error(str(exc))
        raise


if __name__ == "__main__":
    main()
