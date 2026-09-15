import os, tempfile, importlib

def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ['PAPER_BOT_DATA_DIR'] = d
        import common
        import trade_executor
        importlib.reload(common); importlib.reload(trade_executor)
        state = trade_executor.default_state()
        assert state['starting_equity_usd'] == 10.0
        assert trade_executor.PAPER_LOG_PATH.startswith(d)
        trade_executor.save_paper_log(state)
        assert os.path.exists(os.path.join(d, 'paper_trades.json'))
    print('cloud smoke test passed')

if __name__ == '__main__': main()
