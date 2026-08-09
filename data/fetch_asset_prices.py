"""
Automated Asset Price Ingestion
=================================
Closes a capability gap that data/fetch_macro_data.py never covered:
it fetches macro indicators and leaves btc_ret/qqq_ret/spy_ret/gld_ret/
tlt_ret as NaN on every new row. This module is that feed.

Every capability downstream that touches assets (risk_engine,
allocation_engine, btc_forecast_engine's live use, alert_engine's
asset-anomaly check) silently assumed this existed. It didn't.

DATA SOURCE HISTORY — read before assuming this will keep working:
v1 of this module used stooq.com (free, keyless CSV). A real Colab run
on 2026-08-04 found it 404ing; investigation (web search, not
assumption) found stooq started requiring an API key for CSV downloads
in March 2026 for anonymous requests — not a URL parameter bug, a
policy change with no free-tier workaround. Switched to yfinance
instead: also unofficial/unaffiliated with Yahoo (so it can break too
— multiple independent sources describe it as "fragile" and prone to
breaking when Yahoo changes their site), but it's the most widely used
and actively maintained option, meaning breaks tend to get patched
within days by the library maintainers rather than requiring a source
swap. If this breaks again, the fix is the same shape as this one was:
find what still works, swap the fetch function, keep everything
downstream (the sanity checks, the upsert logic) unchanged.

STILL UNTESTED LIVE from here — yfinance is not on this sandbox's
network allowlist either. This is the first thing to test in Colab
after this fix.
"""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, ASSET_RETURN_COLUMNS

YFINANCE_TICKERS = {
    "BTC": "BTC-USD",
    "QQQ": "QQQ",
    "SPY": "SPY",
    "GLD": "GLD",
    "TLT": "TLT",
}
LOOKBACK_DAYS = 400  # need at least 2 monthly closes to compute 1 month of return; generous margin
YFINANCE_PERIOD = "2y"  # yfinance period string covering LOOKBACK_DAYS with comfortable margin


def fetch_yfinance_monthly_close(ticker: str, lookback_days: int = LOOKBACK_DAYS,
                                  period: str = YFINANCE_PERIOD) -> pd.Series:
    """
    Fetches one Yahoo Finance ticker at daily granularity via yfinance,
    resamples to month-end close ourselves (not yfinance's built-in
    monthly interval, so the indexing convention is fully under our
    control and consistent with the rest of this codebase).
    Shared by fetch_macro_data.py's gold fetch (ticker "GC=F") so
    there's one yfinance-calling function in the project, not two.

    BUG FOUND AND FIXED via a real Colab run on 2026-08-04: naive
    `.resample("ME").last()` creates a bucket for the CURRENT,
    still-in-progress month too, labeled with that month's end date,
    but populated with whatever the latest trading day's close happens
    to be — not a real month-end price. On that run this showed up
    obviously here (date came back "2026-08-31" while it was still
    August 4th) but ALSO silently affected fetch_macro_data.py's gold
    fetch, which shares this function: gold_yoy was computed from that
    same contaminated in-progress-August price, even though the overall
    row was correctly labeled June 2026 by unrelated logic (the FRED
    series' own natural publication lag). Fixed by dropping any month
    that hasn't actually finished yet — asset price data has no
    reporting lag like FRED does, so this exclusion has to be explicit.
    """
    import yfinance as yf
    hist = yf.Ticker(ticker).history(period=period, interval="1d")
    if hist.empty or "Close" not in hist.columns:
        raise ValueError(f"yfinance returned no usable data for {ticker}")
    series = hist["Close"].dropna()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    cutoff = datetime.now() - timedelta(days=lookback_days)
    monthly = series[series.index >= cutoff].resample("ME").last().dropna()
    current_period = pd.Timestamp.now().to_period("M")
    monthly = monthly[monthly.index.to_period("M") < current_period]
    return monthly


def compute_monthly_returns(prices: dict) -> dict:
    """
    prices: dict mapping asset name (e.g. "BTC") to a monthly-close pd.Series.
    Returns {asset: latest_month_return} for the most recent month each
    series has at least 2 observations for (need t and t-1 to compute a return).
    """
    returns = {}
    for asset, series in prices.items():
        if len(series) < 2:
            raise ValueError(f"{asset}: need >=2 monthly closes to compute a return, got {len(series)}")
        returns[asset] = float(series.iloc[-1] / series.iloc[-2] - 1)
    return returns


def sanity_check_return(asset: str, ret: float, max_abs_monthly_return: float = 0.90) -> None:
    """
    Value sanity check (self-monitoring capability): a single-month
    return beyond +/-90% is almost certainly a data error (wrong
    column parsed, split/dividend not adjusted, wrong ticker), not a
    real market move, for any of these 5 assets. Raises rather than
    silently ingesting a value that would corrupt every downstream
    statistic (regime-conditional means, backtests, recommendations).
    """
    if abs(ret) > max_abs_monthly_return:
        raise ValueError(
            f"{asset}: monthly return {ret:.1%} exceeds the {max_abs_monthly_return:.0%} sanity "
            f"bound — likely a data error (bad ticker, unadjusted split/dividend, parsing bug), "
            f"not a real market move. Refusing to ingest; investigate before retrying."
        )


def update_asset_prices(dry_run: bool = False) -> dict:
    """
    Fetches fresh prices for every asset in config.ASSET_RETURN_COLUMNS,
    computes the latest monthly return, sanity-checks it, and upserts
    into master_dataset.parquet's asset return columns for the most
    recent common month — filling in what fetch_macro_data.py's
    update leaves blank, not duplicating its date/regime logic.
    """
    prices, fetch_errors = {}, {}
    for asset, ticker in YFINANCE_TICKERS.items():
        try:
            prices[asset] = fetch_yfinance_monthly_close(ticker)
        except Exception as e:
            fetch_errors[asset] = str(e)

    if not prices:
        return {"dry_run": dry_run, "status": "failed", "fetch_errors": fetch_errors,
                "reason": "no asset prices could be fetched"}

    returns = compute_monthly_returns(prices)

    sanity_errors = {}
    for asset, ret in list(returns.items()):
        try:
            sanity_check_return(asset, ret)
        except ValueError as e:
            sanity_errors[asset] = str(e)
            del returns[asset]  # don't ingest a value that failed its sanity check

    latest_date = max(s.index[-1] for s in prices.values())
    latest_date = pd.Timestamp(latest_date).normalize() + pd.offsets.MonthEnd(0)

    master = pd.read_parquet(PATHS["master_dataset"])
    existing_row_mask = master["date"] == latest_date

    if dry_run:
        return {
            "dry_run": True, "date": str(latest_date.date()), "returns": returns,
            "fetch_errors": fetch_errors, "sanity_errors": sanity_errors,
            "row_exists_for_this_month": bool(existing_row_mask.any()),
        }

    if not existing_row_mask.any():
        # macro update hasn't created this month's row yet — create a minimal one;
        # fetch_macro_data.py will fill in macro/regime columns on its own next run
        new_row = {col: np.nan for col in master.columns}
        new_row["date"] = latest_date
        master = pd.concat([master, pd.DataFrame([new_row])], ignore_index=True)
        existing_row_mask = master["date"] == latest_date

    for asset, ret in returns.items():
        col = ASSET_RETURN_COLUMNS[asset]
        master.loc[existing_row_mask, col] = ret

    master = master.sort_values("date").reset_index(drop=True)
    master.to_parquet(PATHS["master_dataset"], index=False)

    return {
        "dry_run": False,
        "date_updated": str(latest_date.date()),
        "returns_written": returns,
        "fetch_errors": fetch_errors,
        "sanity_errors": sanity_errors,
        "rows_in_dataset": len(master),
    }


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    result = update_asset_prices(dry_run=dry)
    import json
    print(json.dumps(result, indent=2, default=str))
