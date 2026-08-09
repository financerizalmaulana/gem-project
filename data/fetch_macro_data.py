"""
Automated Macro Data Ingestion
================================
Closes the #1 gap from the audit: master_dataset.parquet was a static
snapshot with nothing to refresh it. This module fetches fresh data
from FRED (Federal Reserve Economic Data — free, official, stable
API) and appends new monthly rows, recomputing regime + everything
downstream automatically.

LIVE TEST HISTORY (2026-08-04, real Colab run — first real execution
of any external fetch in this project):
  - 9 of 10 FRED series worked correctly on the first try: cpi,
    fed_rate, unemployment, oil, dxy, us10y, vix, indpro, neworder.
    All plausible values, no errors.
  - GPR fetch (the fragile Excel-file source) also worked: "ok".
  - is_new_month correctly returned False — FRED's June 2026 data was
    still the latest available in early August due to normal
    publication lag, not a bug.
  - Gold failed: the stooq.com fallback 404'd. Investigated (web
    search, not assumption) and found stooq started requiring an API
    key for CSV downloads in March 2026 — a policy change, not a URL
    parameter bug (an i=m -> i=d attempt did NOT fix it). Switched to
    yfinance instead (see fetch_gold_series below and
    data/fetch_asset_prices.py's module docstring). This yfinance
    switch is NOT yet live-tested — it's the next thing to verify.

What is NOT yet verified: yfinance's actual reachability/behavior from
a real environment, that your FRED API key works, or that any series
gets renamed/discontinued again after this was written (exactly what
happened to gold twice now — first FRED discontinued it, then stooq
paywalled its replacement — expect to revisit data sources
periodically; this is a normal maintenance reality of free data feeds,
not a one-time fix).

Setup: get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html
and set it as the FRED_API_KEY environment variable.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, MACRO_FEATURES

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# verified via web_search run in this session on 2026-07-31 (actually executed,
# not recalled from memory) — see chat for the search that caught GOLD being broken
FRED_SERIES = {
    "cpi":          "CPIAUCSL",       # CPI-U, monthly index
    "fed_rate":     "FEDFUNDS",       # Effective Federal Funds Rate, monthly %
    "unemployment": "UNRATE",         # Unemployment rate, monthly %
    "oil":          "MCOILWTICO",     # WTI crude, monthly $
    # "gold" removed from here — GOLDPMGBD228NLBM is CONFIRMED discontinued by
    # FRED (their own blog: this series' "data have been removed from the FRED
    # database"). Gold now comes from fetch_gold_series() below (yfinance,
    # ticker GC=F), not FRED. Fetched and merged separately in update_master_dataset().
    "dxy":          "DTWEXBGS",       # Nominal Broad US Dollar Index, daily
    "us10y":        "DGS10",          # 10-Year Treasury yield, daily %
    "vix":          "VIXCLS",         # VIX, daily
    "indpro":       "INDPRO",         # Industrial production index, monthly
    "neworder":     "DGORDER",        # Durable goods new orders, monthly $
}
GOLD_YFINANCE_TICKER = "GC=F"  # COMEX gold futures — standard free proxy for spot gold price.
                                # v1 of this used stooq.com; a real Colab run on 2026-08-04 found
                                # stooq now requires an API key for CSV downloads (confirmed via
                                # web search, not a URL-parameter bug). Switched to yfinance —
                                # see data/fetch_asset_prices.py's module docstring for the full
                                # history and the honest caveat that yfinance can break too.
# Geopolitical Risk Index is NOT on FRED — sourced separately from
# Caldara & Iacoviello's public dataset. This is the single most
# fragile part of this pipeline (an Excel file on an academic's
# personal site, not a stable REST API) — see fetch_gpr_series().
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"

LOOKBACK_DAYS = 900  # ~30 months — enough to compute YoY/6m/ratio transforms fresh each run


def fetch_fred_series(series_id: str, api_key: str, lookback_days: int = LOOKBACK_DAYS) -> pd.Series:
    """Fetches one FRED series, returns a monthly-resampled pd.Series indexed by month-end date."""
    import requests  # imported here, not at module level, so this file can be imported
                      # for its transform functions even where `requests` isn't installed
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    resp = requests.get(FRED_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    obs = resp.json()["observations"]
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).set_index("date")["value"]
    monthly = df.resample("ME").last().dropna()  # last observation of each month
    return monthly


def fetch_gold_series(lookback_days: int = LOOKBACK_DAYS) -> pd.Series:
    """
    Replacement for the discontinued FRED gold series (GOLDPMGBD228NLBM).
    Reuses fetch_yfinance_monthly_close from fetch_asset_prices.py rather
    than duplicating fetch logic — one yfinance-calling function in the
    project, not two. See that module's docstring for the stooq -> yfinance
    switch history. Ticker: COMEX gold futures (GC=F), a standard free
    proxy for spot gold price and close enough for a YoY % change feature.
    """
    from data.fetch_asset_prices import fetch_yfinance_monthly_close
    return fetch_yfinance_monthly_close(GOLD_YFINANCE_TICKER, lookback_days=lookback_days,
                                         period="3y")  # 900-day lookback needs >2y of yfinance period coverage


def fetch_gpr_series(lookback_days: int = LOOKBACK_DAYS) -> pd.Series:
    """
    Best-effort fetch of the Caldara-Iacoviello Geopolitical Risk Index.
    This is a personal academic page serving a downloadable Excel file,
    not a stable API — expect this to be the first thing that breaks.
    Raises on failure; caller should catch and decide on a fallback
    (e.g. carry forward the last known gpr_ratio with a warning) rather
    than let one fragile indicator take down the whole pipeline.
    """
    import requests
    resp = requests.get(GPR_URL, timeout=30)
    resp.raise_for_status()
    from io import BytesIO
    df = pd.read_excel(BytesIO(resp.content))
    date_col = next(c for c in df.columns if "date" in c.lower() or "month" in c.lower())
    value_col = next(c for c in df.columns if c.upper() == "GPR")
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)[value_col].dropna()
    cutoff = datetime.now() - timedelta(days=lookback_days)
    return df[df.index >= cutoff].resample("ME").last().dropna()


def compute_yoy_pct(series: pd.Series) -> float:
    """12-month percent change, using the latest value vs. ~12 months prior."""
    if len(series) < 13:
        raise ValueError(f"need >=13 monthly observations for YoY, got {len(series)}")
    latest = series.iloc[-1]
    year_ago = series.iloc[-13]
    return (latest / year_ago - 1) * 100


def compute_6m_diff(series: pd.Series) -> float:
    """6-month level difference (percentage points), e.g. for rates."""
    if len(series) < 7:
        raise ValueError(f"need >=7 monthly observations for 6m diff, got {len(series)}")
    return float(series.iloc[-1] - series.iloc[-7])


def compute_trailing_ratio(series: pd.Series, window: int = 12) -> float:
    """Current value / trailing N-month average — used for vix_ratio, gpr_ratio."""
    if len(series) < window + 1:
        raise ValueError(f"need >={window + 1} monthly observations for ratio, got {len(series)}")
    trailing_avg = series.iloc[-(window + 1):-1].mean()
    return float(series.iloc[-1] / trailing_avg)


def compute_latest_features(raw: dict) -> dict:
    """
    raw: dict mapping the keys in FRED_SERIES (+ "gold", "gpr") to monthly
    pd.Series. "gold" and "gpr" are optional — both come from fragile
    non-FRED sources (see module docstring) and may be absent if their
    fetch failed; the caller (update_master_dataset) fills a fallback
    value in that case rather than failing the whole update.
    Returns a dict with exactly the MACRO_FEATURES keys.
    """
    return {
        "cpi_yoy":       compute_yoy_pct(raw["cpi"]),
        "fed_6m":        compute_6m_diff(raw["fed_rate"]),
        "unemp_6m":      compute_6m_diff(raw["unemployment"]),
        "oil_yoy":       compute_yoy_pct(raw["oil"]),
        "gold_yoy":      compute_yoy_pct(raw["gold"]) if "gold" in raw else np.nan,
        "dxy_yoy":       compute_yoy_pct(raw["dxy"]),
        "us10y_6m":      compute_6m_diff(raw["us10y"]),
        "vix_ratio":     compute_trailing_ratio(raw["vix"]),
        "gpr_ratio":     compute_trailing_ratio(raw["gpr"]) if "gpr" in raw else np.nan,
        "indpro_yoy":    compute_yoy_pct(raw["indpro"]),
        "neworder_yoy":  compute_yoy_pct(raw["neworder"]),
    }


def update_master_dataset(fred_api_key: str, dry_run: bool = False) -> dict:
    """
    Fetches fresh data, computes the latest feature row, and upserts it
    into master_dataset.parquet (by date — re-running for a month that's
    already present overwrites that row rather than duplicating it).
    Recomputes cluster_id/regime for the new row via the canonical
    RegimeEngine so it's never out of sync with the rest of the system.
    """
    from engines.regime_engine import RegimeEngine

    raw = {key: fetch_fred_series(series_id, fred_api_key) for key, series_id in FRED_SERIES.items()}

    gpr_status = "ok"
    try:
        raw["gpr"] = fetch_gpr_series()
    except Exception as e:
        gpr_status = f"FAILED ({e}) — falling back to last known gpr_ratio, see note below"

    gold_status = "ok"
    try:
        raw["gold"] = fetch_gold_series()
    except Exception as e:
        gold_status = f"FAILED ({e}) — falling back to last known gold_yoy, see note below"

    master = pd.read_parquet(PATHS["master_dataset"])
    features = compute_latest_features(raw)  # "gold"/"gpr" simply absent from raw if their fetch failed -> NaN

    def _fallback_from_history(col: str):
        return float(master[col].dropna().iloc[-1]) if col in master.columns and master[col].notna().any() else np.nan

    if gold_status != "ok":
        features["gold_yoy"] = _fallback_from_history("gold_yoy")
    if gpr_status != "ok":
        features["gpr_ratio"] = _fallback_from_history("gpr_ratio")

    latest_date = min(s.index[-1] for s in raw.values() if len(s) > 0)
    latest_date = pd.Timestamp(latest_date).normalize() + pd.offsets.MonthEnd(0)
    is_new_month = latest_date not in set(master["date"])

    new_row = {"date": latest_date, **features}

    engine = RegimeEngine()
    detection = engine.detect(pd.Series(new_row))
    new_row["cluster_id"] = detection["cluster_id"]
    new_row["regime"] = detection["regime"]
    # asset return columns are left NaN here — they come from a separate
    # asset price feed, not FRED; see risk_engine's ASSET_RETURN_COLUMNS
    for col in ["btc_ret", "qqq_ret", "spy_ret", "gld_ret", "tlt_ret"]:
        new_row.setdefault(col, np.nan)

    if dry_run:
        return {"dry_run": True, "new_row": new_row, "gpr_status": gpr_status, "gold_status": gold_status,
                "is_new_month": is_new_month}

    master = master[master["date"] != latest_date]  # remove existing row for this month, if any
    master = pd.concat([master, pd.DataFrame([new_row])], ignore_index=True)
    master = master.sort_values("date").reset_index(drop=True)
    master.to_parquet(PATHS["master_dataset"], index=False)

    return {
        "dry_run": False,
        "date_updated": str(latest_date.date()),
        "is_new_month": is_new_month,
        "regime": detection["regime"],
        "confidence": detection["confidence_score"],
        "gpr_status": gpr_status,
        "gold_status": gold_status,
        "rows_in_dataset": len(master),
    }


if __name__ == "__main__":
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("ERROR: set the FRED_API_KEY environment variable (free key: "
              "https://fred.stlouisfed.org/docs/api/api_key.html)")
        sys.exit(1)
    dry = "--dry-run" in sys.argv
    result = update_master_dataset(api_key, dry_run=dry)
    print(json.dumps(result, indent=2, default=str))
