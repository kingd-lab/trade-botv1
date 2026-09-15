#!/usr/bin/env python3
import os
import json
import logging
import tempfile
import requests
from datetime import datetime, timezone

DATA_DIR = os.environ.get("PAPER_BOT_DATA_DIR", "/tmp/paper-bot-data")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_PATH = os.path.join(DATA_DIR, "bot.log")
CIRCUIT_STATE_PATH = os.path.join(DATA_DIR, "circuit_state.json")
WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL")


def get_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh = logging.FileHandler(LOG_PATH); fh.setFormatter(fmt); logger.addHandler(fh)
    sh = logging.StreamHandler(); sh.setFormatter(fmt); logger.addHandler(sh)
    return logger


def send_alert(message):
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=5)
    except requests.RequestException:
        pass


class CircuitBreaker:
    def __init__(self, max_consecutive_errors=5, max_consecutive_losses=3):
        self.max_consecutive_errors = max_consecutive_errors
        self.max_consecutive_losses = max_consecutive_losses
        self.state = self._load()

    def _load(self):
        if os.path.exists(CIRCUIT_STATE_PATH):
            try:
                with open(CIRCUIT_STATE_PATH) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {"consecutive_errors": 0, "consecutive_losses": 0, "tripped": False, "tripped_reason": None, "tripped_at": None}

    def _save(self):
        fd, tmp = tempfile.mkstemp(prefix="circuit_", suffix=".json", dir=DATA_DIR)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.state, f, indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, CIRCUIT_STATE_PATH)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def is_tripped(self): return bool(self.state["tripped"])

    def _trip(self, reason):
        self.state.update({"tripped": True, "tripped_reason": reason, "tripped_at": datetime.now(timezone.utc).isoformat()})
        self._save(); send_alert(f"Paper bot circuit breaker tripped: {reason}")

    def record_error(self, detail=""):
        self.state["consecutive_errors"] += 1
        if self.state["consecutive_errors"] >= self.max_consecutive_errors:
            self._trip(f"{self.state['consecutive_errors']} consecutive errors: {detail}")
        else: self._save()

    def record_success(self):
        self.state["consecutive_errors"] = 0; self._save()

    def record_trade_result(self, pnl_usd):
        if pnl_usd < 0:
            self.state["consecutive_losses"] += 1
            if self.state["consecutive_losses"] >= self.max_consecutive_losses:
                self._trip(f"{self.state['consecutive_losses']} consecutive losing paper trades")
                return
        else: self.state["consecutive_losses"] = 0
        self._save()

    def reset(self):
        self.state = {"consecutive_errors": 0, "consecutive_losses": 0, "tripped": False, "tripped_reason": None, "tripped_at": None}
        self._save()
