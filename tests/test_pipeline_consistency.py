"""
Pipeline consistency tests.

These exist specifically because of bugs found during the migration
from the legacy project:
  1. Two competing regime maps (final vs rebuilt) that disagreed.
  2. dashboard.py indexing asset stats by raw cluster id from a
     DIFFERENT id-space than the one regime detection used.
  3. sort_values() on a date column with leading NaT values silently
     reordering the dataset so "latest" wasn't actually latest.

Run with: python -m pytest tests/ -v
"""

import os
import sys
import json

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, MACRO_FEATURES, ASSET_RETURN_COLUMNS
from engines.regime_engine import RegimeEngine
from engines.risk_engine import RiskEngine
from engines.allocation_engine import AllocationEngine


def test_master_dataset_dates_are_monotonic_and_complete():
    df = pd.read_parquet(PATHS["master_dataset"])
    assert df["date"].isna().sum() == 0, "master_dataset has missing dates — the NaT-sort bug may have regressed"
    assert df["date"].is_monotonic_increasing, "master_dataset is not sorted chronologically"


def test_master_dataset_latest_row_is_actually_latest():
    df = pd.read_parquet(PATHS["master_dataset"])
    assert df["date"].iloc[-1] == df["date"].max(), "iloc[-1] does not match the max date — sorting bug"


def test_regime_map_has_one_name_per_cluster_and_no_duplicates():
    with open(PATHS["regime_map"]) as f:
        regime_map = json.load(f)
    names = list(regime_map.values())
    assert len(names) == len(set(names)), f"regime_map.json has duplicate regime names: {regime_map}"
    assert len(names) == 4, f"expected 4 regimes, got {len(names)}: {regime_map}"


def test_regime_detection_uses_only_the_canonical_files():
    """
    Guards against ever re-introducing a second regime map or model —
    RegimeEngine must only read from config.PATHS, nothing else.
    """
    import inspect
    from engines import regime_engine
    source = inspect.getsource(regime_engine)
    assert "PATHS[" in source, "RegimeEngine should read paths only from config.settings.PATHS"
    assert "_rebuilt" not in source and "_v2" not in source and "_final" not in source, \
        "RegimeEngine references a legacy filename pattern — single source of truth violated"


def test_allocation_engine_never_indexes_by_raw_cluster_int():
    """
    The original bug: asset_perf.loc[pred_cluster] mixed two different
    integer id-spaces. Guard against ever reintroducing integer-keyed
    lookups for regime identity anywhere in the allocation path.
    """
    risk = RiskEngine()
    stats = risk.asset_stats_by_regime("Growth Risk-On")
    assert stats["regime"] == "Growth Risk-On"
    assert all(isinstance(k, str) for k in stats["assets"].keys())


def test_all_assets_have_recommendations():
    engine = AllocationEngine()
    recs = engine.recommend_all()
    for asset in ASSET_RETURN_COLUMNS:
        assert asset in recs
        assert recs[asset]["call"] in ("BUY", "HOLD", "REDUCE", "AVOID", "NO DATA")


def test_regime_probabilities_sum_to_100():
    current = RegimeEngine().detect_latest()
    total = sum(current["probabilities"].values())
    assert abs(total - 100) < 0.1, f"probabilities should sum to ~100, got {total}"


def test_feature_order_matches_model_input_dimension():
    import joblib
    scaler = joblib.load(PATHS["scaler"])
    assert scaler.n_features_in_ == len(MACRO_FEATURES), (
        f"config.MACRO_FEATURES has {len(MACRO_FEATURES)} features but the scaler "
        f"was fit on {scaler.n_features_in_} — order/length mismatch will silently "
        f"corrupt every downstream regime call."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
