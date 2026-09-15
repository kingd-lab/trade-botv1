#!/usr/bin/env python3
"""Single-cycle paper runner: discover once -> open paper positions -> manage exits."""
import time
import traceback
from common import get_logger, CircuitBreaker, send_alert
import token_screener
import trade_executor
import position_manager

log = get_logger("runner")
LOOP_INTERVAL_SECONDS = 300
POSITION_CHECK_EVERY_N_CYCLES = 1
MAX_CONSECUTIVE_ERRORS = 5
MAX_CONSECUTIVE_LOSSES = 3


def run_cycle(cycle_num, breaker):
    log.info(f"--- Cycle {cycle_num} ---")
    candidates = token_screener.discover_candidates()
    log.info(f"Found {len(candidates)} candidates.")
    trade_executor.execute_candidates(candidates)  # same candidate set; no second discovery
    if cycle_num % POSITION_CHECK_EVERY_N_CYCLES == 0:
        for trade in position_manager.check_positions():
            breaker.record_trade_result(float(trade["pnl_usd"]))
            if float(trade["pnl_usd"]) <= -0.15:
                send_alert(f"Paper loss warning: {trade['symbol']} ${trade['pnl_usd']:+.2f} ({trade['exit_reason']})")


def main():
    breaker = CircuitBreaker(MAX_CONSECUTIVE_ERRORS, MAX_CONSECUTIVE_LOSSES)
    if breaker.is_tripped():
        log.error(f"Circuit breaker already tripped: {breaker.state['tripped_reason']}")
        return
    cycle = 0
    while not breaker.is_tripped():
        cycle += 1
        try:
            run_cycle(cycle, breaker); breaker.record_success()
        except Exception as e:
            log.error(f"Cycle failed: {e}\n{traceback.format_exc()}")
            breaker.record_error(str(e))
        if not breaker.is_tripped():
            time.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
