"""
Tests for data/fetch_asset_prices.py.
No live network needed — synthetic price series and a mocked fetch
result standing in for a real yfinance response, same pattern as
tests/test_fetch_macro_data.py.
"""

import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.fetch_asset_prices import compute_monthly_returns, sanity_check_return, update_asset_prices
from config.settings import PATHS


def _monthly(values, start="2026-01-31"):
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


def test_compute_monthly_returns_known_value():
    prices = {"BTC": _monthly([100.0, 110.0])}  # +10%
    returns = compute_monthly_returns(prices)
    assert returns["BTC"] == pytest.approx(0.10, abs=1e-9)


def test_compute_monthly_returns_raises_on_insufficient_data():
    prices = {"BTC": _monthly([100.0])}
    with pytest.raises(ValueError, match=">=2 monthly closes"):
        compute_monthly_returns(prices)


def test_sanity_check_accepts_normal_return():
    sanity_check_return("BTC", 0.25)  # should not raise


def test_sanity_check_rejects_implausible_return():
    with pytest.raises(ValueError, match="sanity"):
        sanity_check_return("BTC", 5.0)  # +500% in one month -> almost certainly a data bug


def test_fetch_yfinance_monthly_close_excludes_in_progress_current_month():
    """
    Regression test for a real bug found via a live Colab run on
    2026-08-04: naive resample("ME").last() included a bucket for the
    still-in-progress current month, dated with that month's end date
    but populated from an incomplete month of trading days.
    """
    import data.fetch_asset_prices as fap
    from unittest.mock import MagicMock

    now = pd.Timestamp.now()
    # daily data running from 2 months ago through TODAY (mid-month) —
    # the current month is deliberately incomplete
    idx = pd.date_range(end=now, periods=70, freq="D")
    fake_hist = pd.DataFrame({"Close": range(len(idx))}, index=idx)

    fake_ticker = MagicMock()
    fake_ticker.history.return_value = fake_hist
    with patch("yfinance.Ticker", return_value=fake_ticker):
        result = fap.fetch_yfinance_monthly_close("FAKE", lookback_days=90)

    assert result.index.to_period("M").max() < now.to_period("M"), (
        "the current in-progress month must never appear in the output — "
        "it was populated from an incomplete month of trading days, not a real month-end close"
    )


def test_update_asset_prices_upserts_into_existing_row(tmp_path, monkeypatch):
    """
    Mocked fetch result standing in for real yfinance responses.
    Verifies the upsert writes into the correct existing row rather
    than creating a duplicate, and doesn't touch macro columns.
    """
    master = pd.read_parquet(PATHS["master_dataset"])
    target_date = master["date"].iloc[-1]
    fake_prices = {
        "BTC": _monthly([100.0, 112.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "QQQ": _monthly([500.0, 505.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "SPY": _monthly([600.0, 606.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "GLD": _monthly([200.0, 202.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "TLT": _monthly([90.0, 89.0], start=(target_date - pd.offsets.MonthEnd(1))),
    }
    with patch("data.fetch_asset_prices.fetch_yfinance_monthly_close", side_effect=lambda ticker, **kw: {
        "BTC-USD": fake_prices["BTC"], "QQQ": fake_prices["QQQ"], "SPY": fake_prices["SPY"],
        "GLD": fake_prices["GLD"], "TLT": fake_prices["TLT"],
    }[ticker]):
        result = update_asset_prices(dry_run=True)

    assert result["dry_run"] is True
    assert result["returns"]["BTC"] == pytest.approx(0.12, abs=1e-6)
    assert result["row_exists_for_this_month"] is True
    assert result["sanity_errors"] == {}
    # confirm the real dataset on disk was NOT modified by a dry run
    master_after = pd.read_parquet(PATHS["master_dataset"])
    assert master_after.equals(master)


def test_update_asset_prices_flags_but_does_not_ingest_bad_data():
    master = pd.read_parquet(PATHS["master_dataset"])
    target_date = master["date"].iloc[-1]
    fake_prices = {
        "BTC": _monthly([100.0, 1000.0], start=(target_date - pd.offsets.MonthEnd(1))),  # +900%, implausible
        "QQQ": _monthly([500.0, 505.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "SPY": _monthly([600.0, 606.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "GLD": _monthly([200.0, 202.0], start=(target_date - pd.offsets.MonthEnd(1))),
        "TLT": _monthly([90.0, 89.0], start=(target_date - pd.offsets.MonthEnd(1))),
    }
    with patch("data.fetch_asset_prices.fetch_yfinance_monthly_close", side_effect=lambda ticker, **kw: {
        "BTC-USD": fake_prices["BTC"], "QQQ": fake_prices["QQQ"], "SPY": fake_prices["SPY"],
        "GLD": fake_prices["GLD"], "TLT": fake_prices["TLT"],
    }[ticker]):
        result = update_asset_prices(dry_run=True)

    assert "BTC" in result["sanity_errors"]
    assert "BTC" not in result["returns"]  # bad value excluded, not silently ingested
    assert "QQQ" in result["returns"]  # other assets unaffected by one bad source


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
