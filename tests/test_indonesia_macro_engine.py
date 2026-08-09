"""
Tests for engines/indonesia_macro_engine.py assess() logic.
No live network needed — synthetic series with known properties.
"""

import os
import sys

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.indonesia_macro_engine import IndonesiaMacroEngine


def _monthly(values, start="2024-01-31"):
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.Series(values, index=idx)


def _quarterly(values, start="2022-03-31"):
    idx = pd.date_range(start=start, periods=len(values), freq="QE")
    return pd.Series(values, index=idx)


def test_assess_detects_rising_inflation_and_hiking_stance():
    engine = IndonesiaMacroEngine()
    raw = {
        "id_cpi": _monthly([100 * (1.005 ** i) for i in range(16)]),  # ~6%+ annualized -> "rising"
        "bi_rate": _monthly([4.0, 4.0, 4.0, 4.25, 4.5, 4.75, 5.0]),   # rising over last 3m -> "hiking"
        "usdidr": _quarterly([15000, 15100, 15300, 15600, 16000]),     # depreciating -> "weakening"
        "id_gdp": _quarterly([100 * (1.01 ** i) for i in range(6)]),
        "id_trade_balance": _monthly([1000, 1000, 1000, 1200]),        # growing surplus -> "widening surplus"
    }
    result = engine.assess(raw)
    assert result["inflation_read"] == "rising"
    assert result["policy_stance"] == "hiking"
    assert result["idr_direction_3m"] == "weakening"
    assert result["trade_balance_read"] == "widening surplus"
    assert result["not_sourced"] == []  # trade balance source was found and closed this session


def test_assess_detects_stable_conditions():
    engine = IndonesiaMacroEngine()
    raw = {
        "id_cpi": _monthly([100 * (1.002 ** i) for i in range(16)]),  # ~2.4% annualized -> "contained"
        "bi_rate": _monthly([5.0] * 7),  # unchanged -> "holding"
        "usdidr": _quarterly([15500, 15510, 15490, 15505, 15500]),  # flat -> "stable"
        "id_gdp": _quarterly([100 * (1.005 ** i) for i in range(6)]),
        "id_trade_balance": _monthly([1000, 1000, 1000, 1000]),  # unchanged -> "stable"
    }
    result = engine.assess(raw)
    assert result["inflation_read"] == "contained"
    assert result["policy_stance"] == "holding"
    assert result["idr_direction_3m"] == "stable"
    assert result["trade_balance_read"] == "stable"


def test_assess_reports_trade_balance_deficit():
    engine = IndonesiaMacroEngine()
    raw = {
        "id_cpi": _monthly([100.0] * 16),
        "bi_rate": _monthly([5.0] * 7),
        "usdidr": _quarterly([15500.0] * 5),
        "id_gdp": _quarterly([100.0] * 6),
        "id_trade_balance": _monthly([-500, -600, -550, -700]),  # negative -> "deficit"
    }
    result = engine.assess(raw)
    assert result["trade_balance_read"] == "deficit"
    assert result["trade_balance_rupiah"] < 0


def test_assess_handles_missing_trade_balance_gracefully():
    """Backward compatibility: assess() must not crash if id_trade_balance is absent from raw."""
    engine = IndonesiaMacroEngine()
    raw = {
        "id_cpi": _monthly([100.0] * 16),
        "bi_rate": _monthly([5.0] * 7),
        "usdidr": _quarterly([15500.0] * 5),
        "id_gdp": _quarterly([100.0] * 6),
        # no "id_trade_balance" key at all
    }
    result = engine.assess(raw)
    assert result["trade_balance_read"] == "unknown"
    assert result["trade_balance_rupiah"] is None


def test_assess_always_includes_honest_caveats():
    engine = IndonesiaMacroEngine()
    raw = {
        "id_cpi": _monthly([100.0] * 16),
        "bi_rate": _monthly([5.0] * 7),
        "usdidr": _quarterly([15500.0] * 5),
        "id_gdp": _quarterly([100.0] * 6),
    }
    result = engine.assess(raw)
    assert len(result["caveats"]) >= 2
    assert any("proxy" in c for c in result["caveats"])


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
