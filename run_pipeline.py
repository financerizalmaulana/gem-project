"""
Pipeline Orchestrator — the single entry point a scheduler should call.
==========================================================================
Ties together, in order: macro data refresh -> asset price refresh ->
alert checks -> report generation -> Telegram delivery (alerts, plus a
monthly digest — see DELIVERY DECISION below). This is what closes the
"scheduler / automation layer" gap — not by running a persistent
process (this project has no long-running server), but by being ONE
command that does everything, so any scheduler (cron, GitHub Actions,
a Colab scheduled cell) just needs to run this file.

Reuses every existing engine unchanged — this file contains no new
computation logic, only sequencing.

DELIVERY DECISION (finalized, not left open): alerts are pushed to
Telegram whenever they fire, same as before. In addition, when the
macro refresh lands a genuinely NEW month of data (not just a
same-month update), a short digest — current regime + top asset call
— is also pushed, even with zero alerts. Rationale: this system's
underlying data is monthly, so a message every scheduler run (e.g.
daily) would be noise, but silence every month a real update landed
would mean the "automatic AI analyst" capability never actually
speaks up on its own. Gated on is_new_month so re-running the same
month twice doesn't re-notify.

Usage:
    export FRED_API_KEY=...
    export TELEGRAM_BOT_TOKEN=...      # optional — skips send if unset
    export TELEGRAM_CHAT_ID=...        # optional
    python run_pipeline.py

ENVIRONMENT LIMITATION: end-to-end execution (real FRED/stooq fetch +
real Telegram send) has NOT been run in this sandbox — none of
api.stlouisfed.org, stooq.com, api.telegram.org are reachable here.
Each individual piece (data ingestion math, alert logic, report
generation, Telegram payload/retry logic) is unit-tested separately;
this file's job is just correct sequencing and error isolation
between steps, which IS tested (tests/test_run_pipeline.py) with
every step mocked.
"""

import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.fetch_macro_data import update_master_dataset
from data.fetch_asset_prices import update_asset_prices
from engines.alert_engine import AlertEngine
from engines.allocation_engine import AllocationEngine
from reports.report_generator import generate_report


def run(fred_api_key: str = None, telegram_bot_token: str = None, telegram_chat_id: str = None,
        skip_data_refresh: bool = False) -> dict:
    """
    Each step is isolated in its own try/except: a failure in one step
    (e.g. GPR fetch breaking) should not prevent the report from still
    being generated with whatever data IS available, and should not
    prevent alerts from still being checked and sent. Every step's
    outcome is recorded, not just the last one.
    """
    log = {"steps": {}}
    is_new_month = False

    # --- Step 1a: refresh macro data ---
    if skip_data_refresh:
        log["steps"]["data_refresh"] = {"status": "skipped"}
    elif not fred_api_key:
        log["steps"]["data_refresh"] = {"status": "skipped", "reason": "no FRED_API_KEY provided"}
    else:
        try:
            result = update_master_dataset(fred_api_key)
            log["steps"]["data_refresh"] = {"status": "ok", "result": result}
            is_new_month = bool(result.get("is_new_month"))
        except Exception as e:
            log["steps"]["data_refresh"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    # --- Step 1b: refresh asset prices (independent of FRED — stooq needs no key) ---
    if skip_data_refresh:
        log["steps"]["asset_price_refresh"] = {"status": "skipped"}
    else:
        try:
            result = update_asset_prices()
            log["steps"]["asset_price_refresh"] = {"status": "ok", "result": result}
        except Exception as e:
            log["steps"]["asset_price_refresh"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    # --- Step 2: check alerts ---
    alerts = []
    try:
        alert_engine = AlertEngine()
        alerts = alert_engine.run_all_checks()
        log["steps"]["alerts"] = {"status": "ok", "count": len(alerts), "alerts": alerts}
    except Exception as e:
        log["steps"]["alerts"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    # --- Step 3: generate report ---
    try:
        report_text = generate_report()
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "reports", "latest_report.md")
        with open(report_path, "w") as f:
            f.write(report_text)
        log["steps"]["report"] = {"status": "ok", "path": report_path}
    except Exception as e:
        log["steps"]["report"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    # --- Step 4: build the notification list — alerts, plus a monthly digest if a new month landed ---
    notifications = list(alerts)
    if is_new_month:
        try:
            from engines.regime_engine import RegimeEngine
            current = RegimeEngine().detect_latest()
            top_call = None
            recs = AllocationEngine().recommend_all()
            buys = [a for a, r in recs.items() if r.get("call") == "BUY"]
            top_call = f"BUY: {', '.join(buys)}" if buys else "no BUY calls this month"
            notifications.append({
                "type": "MONTHLY_DIGEST",
                "severity": "low",
                "message": f"Monthly update ({current['date']}): regime is {current['regime']} "
                           f"(confidence {current['confidence_score']}/100). {top_call}.",
            })
            log["steps"]["monthly_digest"] = {"status": "ok"}
        except Exception as e:
            log["steps"]["monthly_digest"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    # --- Step 5: send notification (alerts and/or digest, only if credentials provided) ---
    if not notifications:
        log["steps"]["notification"] = {"status": "skipped", "reason": "nothing to notify"}
    elif not (telegram_bot_token and telegram_chat_id):
        log["steps"]["notification"] = {"status": "skipped", "reason": "no Telegram credentials provided"}
    else:
        try:
            send_result = AlertEngine.send_via_telegram(telegram_bot_token, telegram_chat_id, notifications)
            log["steps"]["notification"] = {"status": "ok" if send_result["sent"] else "failed", "result": send_result}
        except Exception as e:
            log["steps"]["notification"] = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}

    log["overall_status"] = "ok" if all(
        s["status"] in ("ok", "skipped") for s in log["steps"].values()
    ) else "partial_failure"
    return log


def _clean_env(name: str) -> str:
    """
    Strips whitespace/newlines from an env var before use. Found via a
    real GitHub Actions run: a trailing newline in a copy-pasted
    FRED_API_KEY secret got URL-encoded as %0A and FRED rejected the
    whole request with 400 Bad Request. Copy-pasting secrets into
    GitHub's secret box picking up a trailing newline is an easy,
    common mistake — defending against it here means it can't silently
    break any of the three credentials (FRED key, Telegram token/chat
    id) ever again, regardless of how carefully they're pasted.
    """
    value = os.environ.get(name)
    return value.strip() if value else value


if __name__ == "__main__":
    result = run(
        fred_api_key=_clean_env("FRED_API_KEY"),
        telegram_bot_token=_clean_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_clean_env("TELEGRAM_CHAT_ID"),
        skip_data_refresh="--skip-data-refresh" in sys.argv,
    )
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["overall_status"] == "ok" else 1)
