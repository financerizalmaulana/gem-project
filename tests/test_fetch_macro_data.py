"""
Tests for data/fetch_macro_data.py.

These do NOT hit the real FRED API (this sandbox can't reach it anyway —
see the module docstring). Instead they verify:
  1. The transform math (YoY%, 6m diff, trailing ratio) against synthetic
     series with hand-computed expected values.
  2. The upsert-into-master_dataset logic against a temporary COPY of the
     real master_dataset.parquet, using a mocked fetch result standing in
     for what a real API response would look like.

Run with: python -m pytest tests/test_fetch_macro_data.py -v
"""

import os
import sys
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, MACRO_FEATURES
from data.fetch_macro_data import (
    compute_yoy_pct, compute_6m_diff, compute_trailing_ratio,
    compute_latest_features, update_master_dataset, fetch_fred_series, FRED_SERIES,
)


def _monthly_series(values, start="2024-01-31"):
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


def test_compute_yoy_pct_known_value():
    # 13 months: flat 100 for the first 12, then 110 in month 13 -> +10% YoY
    s = _monthly_series([100.0] * 12 + [110.0])
    assert abs(compute_yoy_pct(s) - 10.0) < 1e-9


def test_compute_6m_diff_known_value():
    # 7 months, value goes from 2.0 to 3.5 -> diff of 1.5
    s = _monthly_series([2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 3.5])
    assert abs(compute_6m_diff(s) - 1.5) < 1e-9


def test_compute_trailing_ratio_known_value():
    # 13 months: trailing 12 average to 20, latest value 30 -> ratio 1.5
    s = _monthly_series([20.0] * 12 + [30.0])
    assert abs(compute_trailing_ratio(s, window=12) - 1.5) < 1e-9


def test_fetch_fred_series_strips_trailing_newline_from_api_key(monkeypatch):
    """
    Regression test for a real bug found via a GitHub Actions run: a
    trailing newline in a copy-pasted FRED_API_KEY GitHub Secret got
    URL-encoded as %0A, and FRED rejected the whole request with
    400 Bad Request. fetch_fred_series must strip the key before use.
    """
    captured_params = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"observations": [{"date": "2024-01-31", "value": "1.0"}]}

    def fake_get(url, params, timeout):
        captured_params.update(params)
        return FakeResponse()

    import data.fetch_macro_data as fmd
    monkeypatch.setattr("requests.get", fake_get)
    fmd.fetch_fred_series("CPIAUCSL", "abc123\n")  # simulate a key with a trailing newline
    assert captured_params["api_key"] == "abc123"  # not "abc123\n"


def test_compute_yoy_raises_on_insufficient_data():
    s = _monthly_series([100.0] * 5)
    with pytest.raises(ValueError):
        compute_yoy_pct(s)


def test_compute_latest_features_returns_all_macro_features():
    raw = {}
    for key in FRED_SERIES:
        raw[key] = _monthly_series([100.0 + i for i in range(13)])
    raw["gpr"] = _monthly_series([90.0 + i for i in range(13)])
    features = compute_latest_features(raw)
    assert set(features.keys()) == set(MACRO_FEATURES)
    assert all(isinstance(v, (int, float, np.floating)) for v in features.values())


def test_update_master_dataset_upserts_without_duplicating(monkeypatch):
    """
    Full integration test of the upsert logic against a REAL copy of
    master_dataset.parquet, with fetch_fred_series/fetch_gpr_series
    mocked out (no network). Verifies: (a) a new month gets appended,
    (b) re-running for the SAME month overwrites rather than duplicates,
    (c) the appended row's regime is computed via the real RegimeEngine
    (not fabricated), (d) dates stay sorted and unique.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_master = os.path.join(tmpdir, "master_dataset.parquet")
        shutil.copy2(PATHS["master_dataset"], tmp_master)
        monkeypatch.setitem(PATHS, "master_dataset", tmp_master)

        original = pd.read_parquet(tmp_master)
        n_before = len(original)
        last_date = original["date"].max()
        next_month_end = (last_date + pd.offsets.MonthEnd(1))

        def fake_fetch_fred_series(series_id, api_key, lookback_days=900):
            # deterministic synthetic monthly series ending at next_month_end
            idx = pd.date_range(end=next_month_end, periods=15, freq="ME")
            return pd.Series(np.linspace(100, 115, 15), index=idx)

        def fake_fetch_gpr_series(lookback_days=900):
            idx = pd.date_range(end=next_month_end, periods=15, freq="ME")
            return pd.Series(np.linspace(90, 95, 15), index=idx)

        monkeypatch.setattr("data.fetch_macro_data.fetch_fred_series", fake_fetch_fred_series)
        monkeypatch.setattr("data.fetch_macro_data.fetch_gpr_series", fake_fetch_gpr_series)

        result1 = update_master_dataset(fred_api_key="fake-key-not-used", dry_run=False)
        after_first = pd.read_parquet(tmp_master)
        assert len(after_first) == n_before + 1, "expected exactly one new row"
        assert after_first["date"].is_monotonic_increasing
        assert after_first["date"].duplicated().sum() == 0
        assert result1["regime"] in ("Crisis", "Disinflation Normal", "Growth Risk-On", "Inflation Shock")

        # re-run for the same synthetic month -> should overwrite, not duplicate
        result2 = update_master_dataset(fred_api_key="fake-key-not-used", dry_run=False)
        after_second = pd.read_parquet(tmp_master)
        assert len(after_second) == n_before + 1, "re-running for the same month duplicated a row"
        assert result1["date_updated"] == result2["date_updated"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
