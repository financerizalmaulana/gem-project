"""
Alert Engine
============
Generates warnings BEFORE things happen, using only what the other
engines already compute — no new modeling here, just thresholds.

This directly targets goal #6/#7 (warnings on watched assets, and on
regime change). The old project had zero automation: dashboard.py was
pull-only (open the browser to see anything). This engine produces a
list of warning dicts; wiring it to actually push to Telegram is a
~10 line addition (see `send_via_telegram` below) using the same bot
token pattern you already use in the personal-finance Telegram bot —
intentionally NOT executed in this sandbox since Telegram's API
domain isn't reachable from this tool's network, so treat the send
function as a template to test in Colab/your own environment.

Run this on a schedule (e.g. daily/weekly cron in Colab or a small
always-on VM) rather than only when the dashboard happens to be open.
"""

import os
import sys
import json
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.regime_engine import RegimeEngine
from engines.transition_engine import TransitionEngine
from engines.allocation_engine import AllocationEngine

# --- tunable thresholds ---
CONFIDENCE_LOW_THRESHOLD = 45.0     # regime confidence below this = "near a boundary" warning
TRANSITION_RISK_THRESHOLD = 25.0    # forward probability of Crisis/Inflation Shock above this = warning
STALE_DATA_DAYS = 45                # flag if the dataset hasn't advanced in this many days —
                                     # catches a silently-broken FRED fetch (e.g. discontinued
                                     # series, expired key) before it goes unnoticed for months
REGIME_CHANGE_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                         "data", "processed", "_last_known_regime.json")


class AlertEngine:
    def __init__(self):
        self.regime_engine = RegimeEngine()
        self.transition_engine = TransitionEngine()
        self.allocation_engine = AllocationEngine()

    def check_regime_change(self, current: dict) -> list:
        """Compares current regime against the last time this was run."""
        alerts = []
        last_known = None
        if os.path.exists(REGIME_CHANGE_STATE_FILE):
            with open(REGIME_CHANGE_STATE_FILE) as f:
                last_known = json.load(f).get("regime")

        if last_known is not None and last_known != current["regime"]:
            alerts.append({
                "type": "REGIME_CHANGE",
                "severity": "high",
                "message": f"Regime changed: {last_known} -> {current['regime']} (as of {current['date']})",
            })

        os.makedirs(os.path.dirname(REGIME_CHANGE_STATE_FILE), exist_ok=True)
        with open(REGIME_CHANGE_STATE_FILE, "w") as f:
            json.dump({"regime": current["regime"], "date": current["date"]}, f)

        return alerts

    def check_low_confidence(self, current: dict) -> list:
        if current["confidence_score"] < CONFIDENCE_LOW_THRESHOLD:
            return [{
                "type": "LOW_CONFIDENCE_REGIME",
                "severity": "medium",
                "message": (
                    f"Regime confidence is only {current['confidence_score']}/100 — "
                    f"we may be sitting near a boundary between {current['regime']} and "
                    f"{list(current['probabilities'].keys())[1]}."
                ),
            }]
        return []

    def check_transition_risk(self, current: dict) -> list:
        flags = self.transition_engine.risk_flags(current["regime"], threshold=TRANSITION_RISK_THRESHOLD)
        return [{
            "type": "FORWARD_REGIME_RISK",
            "severity": "medium",
            "message": (
                f"{f['probability_pct']}% probability of moving into "
                f"'{f['regime_at_risk']}' within {f['horizon']}."
            ),
        } for f in flags]

    def check_data_freshness(self, current: dict) -> list:
        """
        Every other check in this engine assumes master_dataset.parquet is
        current. It won't always be — the FRED/stooq/GPR fetches in
        data/fetch_macro_data.py are fragile external sources (one, gold,
        was already found discontinued once). This check makes that
        assumption visible instead of silent.
        """
        from datetime import datetime
        data_date = pd.Timestamp(current["date"])
        days_stale = (pd.Timestamp(datetime.now().date()) - data_date).days
        if days_stale > STALE_DATA_DAYS:
            return [{
                "type": "DATA_STALE",
                "severity": "high",
                "message": (
                    f"master_dataset.parquet's latest row is {current['date']} "
                    f"({days_stale} days old). Every other check below is computed "
                    f"from this same stale data — the data ingestion pipeline "
                    f"(data/fetch_macro_data.py) may be failing silently."
                ),
            }]
        return []

    def check_asset_calls(self) -> list:
        alerts = []
        for asset, rec in self.allocation_engine.recommend_all().items():
            if rec.get("call") in ("AVOID", "REDUCE"):
                alerts.append({
                    "type": "ASSET_CALL",
                    "severity": "medium" if rec["call"] == "REDUCE" else "high",
                    "message": f"{asset}: {rec['call']} (risk-adjusted score {rec['risk_adjusted_score']})",
                })
        return alerts

    def run_all_checks(self) -> list:
        current = self.regime_engine.detect_latest()
        alerts = []
        alerts += self.check_data_freshness(current)
        alerts += self.check_regime_change(current)
        alerts += self.check_low_confidence(current)
        alerts += self.check_transition_risk(current)
        alerts += self.check_asset_calls()
        return alerts

    @staticmethod
    def build_telegram_payload(chat_id: str, alerts: list) -> dict:
        """
        Pure function, no network — separated out so the message format
        can be unit-tested without hitting Telegram. This part IS tested
        (tests/test_alert_engine.py).
        HTML-escaped defensively: parse_mode=HTML makes Telegram reject
        the whole request if any message ever contains an unescaped
        <, >, or & — this hasn't happened yet in the current alert
        messages, but would fail silently-looking (just a 400) the
        moment it did, so escaping now closes that off permanently.
        """
        import html
        text = "\n\n".join(f"[{a['severity'].upper()}] {html.escape(a['message'])}" for a in alerts)
        return {"chat_id": chat_id, "text": f"GEM Alert:\n\n{text}", "parse_mode": "HTML"}

    @staticmethod
    def send_via_telegram(bot_token: str, chat_id: str, alerts: list, max_retries: int = 2) -> dict:
        """
        NOT executed against a real Telegram server in this sandbox —
        api.telegram.org is unreachable from this tool's network
        (confirmed by trying; only pypi/npm/github-class domains are
        allowlisted here). The payload construction and retry logic
        below ARE unit-tested with a mocked `requests.post`
        (tests/test_alert_engine.py::test_send_via_telegram_retries_on_failure).

        BUG FOUND via a real GitHub Actions run on 2026-08-XX: a 400
        error was returned, but `resp.raise_for_status()` alone only
        reports the status code — it discards the JSON body Telegram
        actually sends back with the SPECIFIC reason (e.g. "chat not
        found", "can't parse entities", "bot was blocked by the user").
        Without that, this was undebuggable from the logs alone. Fixed
        below to capture and surface the real reason.
        """
        import requests
        if not alerts:
            return {"sent": False, "reason": "no alerts to send"}

        payload = AlertEngine.build_telegram_payload(chat_id, alerts)
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        last_error = None
        for attempt in range(1, max_retries + 2):
            try:
                resp = requests.post(url, data=payload, timeout=15)
                if not resp.ok:
                    try:
                        telegram_error = resp.json().get("description", resp.text)
                    except Exception:
                        telegram_error = resp.text
                    raise RuntimeError(f"Telegram API error {resp.status_code}: {telegram_error}")
                return {"sent": True, "attempt": attempt, "status_code": resp.status_code}
            except Exception as e:
                last_error = str(e)
                if attempt <= max_retries:
                    time.sleep(2 ** attempt)  # 2s, 4s backoff
        return {"sent": False, "reason": last_error, "attempts": max_retries + 1}


if __name__ == "__main__":
    engine = AlertEngine()
    alerts = engine.run_all_checks()
    print(json.dumps(alerts, indent=2) if alerts else "No alerts triggered.")
