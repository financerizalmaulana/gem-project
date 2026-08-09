"""
GEM Dashboard v2
================
Thin UI layer. ALL computation happens in engines/ — this file only
renders. This is the key architectural fix versus the old
dashboard.py, which computed the current regime one way (via
kmeans_regime.pkl + regime_map_final.pkl, correct) and then indexed
into asset statistics using an incompatible cluster-id space from a
different file (regime_asset_rebuilt.parquet's cluster_rebuilt),
silently showing the wrong regime's asset performance. That class of
bug is structurally prevented here because every panel below asks
regime_engine for the regime NAME once, and every other engine takes
that name as a string — never a raw cluster integer.
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ASSET_RETURN_COLUMNS
from engines.regime_engine import RegimeEngine
from engines.transition_engine import TransitionEngine
from engines.risk_engine import RiskEngine
from engines.allocation_engine import AllocationEngine, FORWARD_HORIZON
from engines.btc_forecast_engine import BTCForecastEngine
from engines.alert_engine import AlertEngine

st.set_page_config(page_title="GEM Dashboard", layout="wide")


@st.cache_resource
def load_engines():
    return {
        "regime": RegimeEngine(),
        "transition": TransitionEngine(),
        "risk": RiskEngine(),
        "allocation": AllocationEngine(),
        "alert": AlertEngine(),
    }


engines = load_engines()
current = engines["regime"].detect_latest()

st.title("GEM Dashboard")
st.caption("v2 — single source of truth, no duplicated cluster-id spaces")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current Regime", current["regime"])
with col2:
    st.metric("Confidence", f"{current['confidence_score']}/100")
with col3:
    st.metric("Data as of", current["date"])

st.divider()

# --- Active warnings, front and center ---
alerts = engines["alert"].run_all_checks()
if alerts:
    st.subheader("⚠️ Active Warnings")
    for a in alerts:
        (st.error if a["severity"] == "high" else st.warning)(a["message"])
    st.divider()

# --- Regime probability ---
st.subheader("Regime Probabilities")
st.bar_chart(current["probabilities"])

st.divider()

# --- Transition forecast (previously computed but never shown) ---
st.subheader("Regime Transition Forecast")
st.caption("Probability of being in each regime N months from now, given the current regime")
transition_forecast = engines["transition"].forecast(current["regime"])
tab_labels = list(transition_forecast.keys())
tabs = st.tabs(tab_labels)
for tab, horizon in zip(tabs, tab_labels):
    with tab:
        st.bar_chart(transition_forecast[horizon])

st.divider()

# --- Asset recommendations (the previously-missing "allocation" feature) ---
st.subheader("Asset Recommendations")
st.caption(f"Blend of current-regime history + {FORWARD_HORIZON} forward transition-weighted return, risk-adjusted for volatility")
allocations = engines["allocation"].recommend_all()
rec_rows = []
for asset, rec in allocations.items():
    if rec.get("call") == "NO DATA":
        continue
    rec_rows.append({
        "Asset": asset,
        "Call": rec["call"],
        "Current regime mean/mo": f"{rec['current_regime_mean_monthly_return_pct']}%",
        f"{FORWARD_HORIZON} forward blend": f"{rec[f'blended_{FORWARD_HORIZON}_forward_return_pct']}%",
        "Volatility": f"{rec['volatility_pct']}%",
        "Score": rec["risk_adjusted_score"],
        "Samples": rec["historical_sample_size"],
    })
st.dataframe(rec_rows, use_container_width=True)

st.divider()

# --- Multi-horizon scenario ranges, any tracked asset (same engine, asset-generic) ---
st.subheader("Multi-Horizon Scenario Ranges")
st.caption("Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction")
selected_asset = st.selectbox("Asset", list(ASSET_RETURN_COLUMNS.keys()), index=0)
asset_forecast = BTCForecastEngine(asset_col=ASSET_RETURN_COLUMNS[selected_asset]).forecast(current["regime"])
asset_forecast_rows = []
for h, data in asset_forecast.items():
    p = data["cumulative_return_pct_percentiles"]
    asset_forecast_rows.append({
        "Horizon": h,
        "p5 (bad case)": f"{p['p5']}%",
        "p25": f"{p['p25']}%",
        "p50 (median)": f"{p['p50']}%",
        "p75": f"{p['p75']}%",
        "p95 (good case)": f"{p['p95']}%",
        "P(positive)": f"{data['prob_positive_pct']}%",
    })
st.dataframe(asset_forecast_rows, use_container_width=True)

st.divider()

# --- Regime history ---
st.subheader("Regime History (last 12 months)")
st.dataframe(engines["regime"].regime_history(12), use_container_width=True)
