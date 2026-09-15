import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import trade_executor
import position_manager


def test_position_size_starts_at_1_50():
    d = trade_executor.default_state()
    assert trade_executor.position_size(d) == 1.5


def test_deployment_cap():
    d = trade_executor.default_state()
    d["cash_usd"] = 7.5
    d["open_positions"] = [{"notional_usd": 1.5}, {"notional_usd": 1.0}]
    assert trade_executor.position_size(d) == 0.5


def test_stop_rule():
    p = {"entry_market_price_usd": 100, "peak_price_usd": 100, "entry_time": "2026-01-01T00:00:00+00:00"}
    _, _, reason = position_manager.evaluate_position(p, 90)
    assert reason == "stop_loss"


def test_take_profit_rule():
    p = {"entry_market_price_usd": 100, "peak_price_usd": 100, "entry_time": "2026-01-01T00:00:00+00:00"}
    _, _, reason = position_manager.evaluate_position(p, 130)
    assert reason == "take_profit"
