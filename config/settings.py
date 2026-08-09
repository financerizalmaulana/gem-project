"""
GEM PROJECT — CONFIG (single source of truth)
================================================
Every path, feature list, and taxonomy used anywhere in the project
must be imported from here. Do not hardcode paths or feature lists
in engines/dashboard/reports — import them from this file instead.

This is the #1 rule that prevents the bugs found in the previous
version of the project (two competing regime maps, three duplicate
scalers, inconsistent feature lists between dashboard.py and the
model training code).
"""

import os

# ---------------------------------------------------------------------
# BASE PATH — auto-detects Google Colab vs local/other environment.
# Override by setting the GEM_BASE_PATH environment variable.
# ---------------------------------------------------------------------
def _detect_base_path() -> str:
    env_override = os.environ.get("GEM_BASE_PATH")
    if env_override:
        return env_override
    colab_path = "/content/drive/MyDrive/GEM_PROJECT"
    if os.path.isdir("/content/drive/MyDrive"):
        return colab_path
    # local/dev fallback: project root (parent of this config/ folder)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_PATH = _detect_base_path()

# ---------------------------------------------------------------------
# Canonical file locations (ONE of each — no _v2, no _rebuilt, no _final)
# ---------------------------------------------------------------------
PATHS = {
    "master_dataset":       os.path.join(BASE_PATH, "data", "processed", "master_dataset.parquet"),
    "scaler":                os.path.join(BASE_PATH, "models", "scaler.pkl"),
    "kmeans":                os.path.join(BASE_PATH, "models", "kmeans.pkl"),
    "regime_map":            os.path.join(BASE_PATH, "models", "regime_map.json"),
    "transition_matrix_dir": os.path.join(BASE_PATH, "models", "transition_matrices"),
}

# ---------------------------------------------------------------------
# Macro features used by the regime clustering model.
# ORDER MATTERS — must match the order the scaler/kmeans were fit on.
# ---------------------------------------------------------------------
MACRO_FEATURES = [
    "cpi_yoy",
    "fed_6m",
    "unemp_6m",
    "oil_yoy",
    "gold_yoy",
    "dxy_yoy",
    "us10y_6m",
    "vix_ratio",
    "gpr_ratio",
    "indpro_yoy",
    "neworder_yoy",
]

# Assets currently tracked for regime-conditional performance / recommendations.
# NOTE: the previous export mixed two asset universes across files
# (btc/eth/gold/spx/dxy in one audit vs btc/qqq/spy/gld/tlt in the live data).
# The live master dataset only has the second set — this is the canonical one.
ASSET_RETURN_COLUMNS = {
    "BTC": "btc_ret",
    "QQQ": "qqq_ret",
    "SPY": "spy_ret",
    "GLD": "gld_ret",
    "TLT": "tlt_ret",
}

# ---------------------------------------------------------------------
# Regime taxonomy. Cluster *index* is arbitrary and can shuffle any time
# the model is refit — never hardcode integer -> name mappings anywhere
# else in the codebase. Always resolve names via regime_engine, which
# derives identity from centroid characteristics against this signature,
# not from a static saved dict alone. This is what the previous project
# was missing, and it's what caused the two contradictory pipelines
# (regime_map_final.pkl vs regime_map_rebuilt.pkl).
# ---------------------------------------------------------------------
REGIME_SIGNATURES = {
    # raw-unit centroid signature, validated against the project's
    # original AUDIT 4 output (2026-06 audit session)
    "Crisis":               {"cpi_yoy": 0.83, "fed_6m": -1.51, "unemp_6m": 6.77,  "oil_yoy": -42.82, "vix_ratio": 1.62, "indpro_yoy": -10.43, "neworder_yoy": -11.38},
    "Disinflation Normal":  {"cpi_yoy": 1.82, "fed_6m": 0.13,  "unemp_6m": -0.42, "oil_yoy": -7.25,  "vix_ratio": 0.93, "indpro_yoy": 0.19,   "neworder_yoy": -0.85},
    "Growth Risk-On":       {"cpi_yoy": 2.83, "fed_6m": -0.19, "unemp_6m": -0.12, "oil_yoy": 8.73,   "vix_ratio": 1.10, "indpro_yoy": 1.92,   "neworder_yoy": 7.31},
    "Inflation Shock":      {"cpi_yoy": 6.16, "fed_6m": 0.86,  "unemp_6m": -0.73, "oil_yoy": 60.64,  "vix_ratio": 0.99, "indpro_yoy": 3.51,   "neworder_yoy": 10.83},
}
SIGNATURE_FEATURES = ["cpi_yoy", "fed_6m", "unemp_6m", "oil_yoy", "vix_ratio", "indpro_yoy", "neworder_yoy"]

TRANSITION_HORIZONS = ["1m", "3m", "6m", "12m"]

# ---------------------------------------------------------------------
# Indonesia macro layer — NOT YET IMPLEMENTED.
# No Indonesian indicators exist anywhere in the source data this
# project was built from. Listed here as the target schema so the
# rest of the codebase (indonesia_macro_engine.py) has a stable
# contract to build against once real data is wired in.
# ---------------------------------------------------------------------
INDONESIA_FEATURES_TARGET = [
    "id_cpi_yoy",       # BPS inflation y/y
    "bi_rate",          # BI 7-Day Reverse Repo Rate
    "usdidr",           # exchange rate
    "id_gdp_yoy",       # BPS GDP growth y/y
    "id_trade_balance", # BPS trade balance
]
