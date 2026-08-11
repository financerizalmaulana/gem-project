"""
Tests for engines/regime_engine.py.

The main thing under test here is a real bug found via a real
Streamlit Cloud deployment: the dashboard showed "Confidence: nan/100"
and regime "Inflation Shock" that didn't match reality. Root cause:
fetch_asset_prices.py can create a placeholder row for a new month
(asset returns filled in, ALL macro columns NaN) before
fetch_macro_data.py has managed to fill that same row in — FRED can
lag 30+ days behind. detect_latest() was using master.iloc[-1]
unconditionally, so it read that incomplete row directly: NaN
macro features -> NaN distances -> NaN confidence, and
np.argmin() on an all-NaN array silently returns index 0, which
happened to be "Inflation Shock" in regime_map.json — a real-looking
but meaningless answer.
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
from engines.regime_engine import RegimeEngine


def _with_temp_master(monkeypatch, mutate_fn):
    """Copies the real master_dataset.parquet, applies mutate_fn to it, points PATHS at the copy."""
    tmpdir = tempfile.mkdtemp()
    tmp_master = os.path.join(tmpdir, "master_dataset.parquet")
    shutil.copy2(PATHS["master_dataset"], tmp_master)
    df = pd.read_parquet(tmp_master)
    df = mutate_fn(df)
    df.to_parquet(tmp_master, index=False)
    monkeypatch.setitem(PATHS, "master_dataset", tmp_master)
    return tmp_master


def test_detect_latest_skips_trailing_placeholder_row(monkeypatch):
    """
    The exact bug: append a row with a real date, real asset returns,
    but every macro feature NaN (mirroring what fetch_asset_prices.py's
    placeholder-row logic produces) and confirm detect_latest() skips
    it and uses the last COMPLETE row instead.
    """
    def add_placeholder_row(df):
        last_complete = df.dropna(subset=MACRO_FEATURES).iloc[-1]
        placeholder = {col: np.nan for col in df.columns}
        placeholder["date"] = last_complete["date"] + pd.offsets.MonthEnd(1)
        placeholder["btc_ret"] = 0.05  # asset return present — this is what makes it a
                                        # "placeholder" row rather than just missing data
        df = pd.concat([df, pd.DataFrame([placeholder])], ignore_index=True)
        return df

    _with_temp_master(monkeypatch, add_placeholder_row)

    engine = RegimeEngine()
    result = engine.detect_latest()

    assert not np.isnan(result["confidence_score"]), "confidence_score must never be NaN"
    assert result["regime"] in ("Crisis", "Disinflation Normal", "Growth Risk-On", "Inflation Shock")
    # must have used the row BEFORE the placeholder, not the placeholder itself
    master = pd.read_parquet(PATHS["master_dataset"])
    last_complete_date = master.dropna(subset=MACRO_FEATURES)["date"].max()
    assert result["date"] == str(last_complete_date.date())


def test_detect_latest_raises_clearly_if_no_complete_row_exists(monkeypatch):
    def blank_out_all_macro(df):
        df.loc[:, MACRO_FEATURES] = np.nan
        return df

    _with_temp_master(monkeypatch, blank_out_all_macro)

    engine = RegimeEngine()
    with pytest.raises(ValueError, match="no row.*complete macro features|complete macro features"):
        engine.detect_latest()


def test_regime_history_skips_rows_with_no_regime_yet(monkeypatch):
    def add_placeholder_row(df):
        last = df.iloc[-1]
        placeholder = {col: np.nan for col in df.columns}
        placeholder["date"] = last["date"] + pd.offsets.MonthEnd(1)
        placeholder["btc_ret"] = 0.05
        # regime stays NaN — this is the placeholder-row signature
        df = pd.concat([df, pd.DataFrame([placeholder])], ignore_index=True)
        return df

    _with_temp_master(monkeypatch, add_placeholder_row)

    engine = RegimeEngine()
    history = engine.regime_history(n_months=5)
    assert history["regime"].isna().sum() == 0, "regime_history must not include rows with no regime yet"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
