"""
Ingestion Health
================
Shared by every data fetcher (fetch_macro_data.py, fetch_asset_prices.py,
indonesia_macro_engine.py) so this logic exists in exactly one place.

Two responsibilities, both aimed at Capability 9 (System Health /
Self-Monitoring) from the roadmap:

1. Consecutive-failure tracking — a single failed fetch is already
   handled per-source with a fall-back-to-last-known-value (see
   fetch_macro_data.py). But a fallback that works forever silently
   hides a permanently broken source. This tracks how many times in a
   row each named source has failed, so alert_engine can escalate once
   a source has been broken for a while, not just once.
2. Sanity bounds — a source can return a technically-successful HTTP
   200 with a garbage value (unit mismatch, decimal-point parsing bug,
   wrong column picked up). This checks freshly computed feature values
   against documented plausible ranges before they're allowed into
   master_dataset.parquet.
"""

import os
import json
from datetime import datetime, timezone

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "processed", "_ingestion_health.json")

# Plausible ranges for values this project computes, in their native units.
# Deliberately wide — this is a last-resort "this is obviously wrong" guard,
# not a tight statistical control. Anything outside these bounds is almost
# certainly a parsing/unit bug, not a real economic event.
SANITY_BOUNDS = {
    "cpi_yoy":       (-20.0, 60.0),    # % YoY — even hyperinflation episodes rarely exceed this for a G20-scale series
    "fed_6m":        (-10.0, 10.0),    # percentage points, 6m change
    "unemp_6m":      (-10.0, 15.0),
    "oil_yoy":       (-95.0, 400.0),   # oil YoY can spike hard (2020 negative prices, 2022 shock)
    "gold_yoy":      (-60.0, 150.0),
    "dxy_yoy":       (-40.0, 40.0),
    "us10y_6m":      (-8.0, 8.0),
    "vix_ratio":     (0.1, 6.0),
    "gpr_ratio":     (0.1, 6.0),
    "indpro_yoy":    (-40.0, 40.0),
    "neworder_yoy":  (-60.0, 100.0),
    "id_cpi_yoy":    (-10.0, 100.0),   # Indonesia has a hyperinflation history (1998) — wider band
    "bi_rate_proxy": (0.0, 30.0),
    "usdidr_level":  (5000.0, 30000.0),
    "id_gdp_yoy":    (-30.0, 30.0),
    "id_trade_balance_yoy": (-500.0, 500.0),
    "asset_monthly_return": (-0.95, 5.0),  # -95% to +500% in a single month — generous, catches unit errors not real crashes
}


def check_sanity(name: str, value: float) -> dict:
    """Returns {"ok": bool, "reason": str|None}. Never raises — a sanity
    check failing should be logged and surfaced, not crash the pipeline."""
    if value is None or (isinstance(value, float) and (value != value)):  # NaN check without importing numpy here
        return {"ok": True, "reason": None}  # NaN is a known/expected fallback state, not a sanity violation
    bounds = SANITY_BOUNDS.get(name)
    if bounds is None:
        return {"ok": True, "reason": f"no sanity bounds defined for '{name}' — add one to SANITY_BOUNDS if this is a recurring field"}
    lo, hi = bounds
    if not (lo <= value <= hi):
        return {"ok": False, "reason": f"{name}={value} outside plausible range [{lo}, {hi}]"}
    return {"ok": True, "reason": None}


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE) as f:
        return json.load(f)


def _save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def record_fetch_attempt(source: str, success: bool, detail: str = "") -> dict:
    """
    Call once per source per pipeline run. Returns the updated record for
    that source, including consecutive_failures — alert_engine reads this
    to decide whether to escalate.
    """
    state = _load_state()
    record = state.get(source, {"consecutive_failures": 0, "last_success": None, "last_attempt": None})

    now = datetime.now(timezone.utc).isoformat()
    record["last_attempt"] = now
    if success:
        record["consecutive_failures"] = 0
        record["last_success"] = now
        record["last_detail"] = detail
    else:
        record["consecutive_failures"] = record.get("consecutive_failures", 0) + 1
        record["last_detail"] = detail

    state[source] = record
    _save_state(state)
    return record


def get_all_health() -> dict:
    return _load_state()


def sources_with_repeated_failures(min_consecutive: int = 3) -> list:
    state = _load_state()
    return [
        {"source": src, "consecutive_failures": rec["consecutive_failures"], "last_detail": rec.get("last_detail", "")}
        for src, rec in state.items()
        if rec.get("consecutive_failures", 0) >= min_consecutive
    ]
