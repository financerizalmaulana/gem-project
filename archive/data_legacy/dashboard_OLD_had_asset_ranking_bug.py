
import streamlit as st
import pandas as pd
import numpy as np
import joblib
from scipy.spatial.distance import cdist

BASE = "/content/drive/MyDrive/GEM_PROJECT"

FEATURES = [
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
    "neworder_yoy"
]

st.set_page_config(
    page_title="GEM Dashboard",
    layout="wide"
)

@st.cache_data
def load_data():

    macro = pd.read_parquet(
        f"{BASE}/macro_regime_final.parquet"
    )

    asset = pd.read_parquet(
        f"{BASE}/regime_asset_rebuilt.parquet"
    )

    return macro, asset

macro, asset = load_data()

scaler = joblib.load(
    f"{BASE}/scaler_regime.pkl"
)

kmeans = joblib.load(
    f"{BASE}/kmeans_regime.pkl"
)

regime_map = joblib.load(
    f"{BASE}/regime_map_final.pkl"
)

latest = macro.iloc[-1]

X = latest[FEATURES].to_frame().T

X_scaled = scaler.transform(X)

dist = cdist(
    X_scaled,
    kmeans.cluster_centers_,
    metric="euclidean"
)[0]

prob = (1 / dist)
prob = prob / prob.sum() * 100

pred_cluster = int(np.argmin(dist))

current_regime = regime_map[pred_cluster]

prob_df = pd.DataFrame({
    "cluster": range(len(dist)),
    "probability": prob
})

prob_df["regime"] = prob_df["cluster"].map(regime_map)

prob_df = prob_df.sort_values(
    "probability",
    ascending=False
)

asset_perf = (
    asset.groupby("cluster_rebuilt")[
        ["btc_ret","qqq_ret","spy_ret","gld_ret","tlt_ret"]
    ]
    .mean()
)

ranking = (
    asset_perf.loc[pred_cluster]
    .sort_values(ascending=False)
)

st.title("GEM Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Current Regime",
        current_regime
    )

with col2:
    st.metric(
        "Top Probability",
        f"{prob_df.iloc[0]['probability']:.2f}%"
    )

with col3:
    st.metric(
        "Date",
        str(latest["date"])
    )

st.divider()

st.subheader("Regime Probabilities")

st.bar_chart(
    prob_df.set_index("regime")["probability"]
)

st.divider()

st.subheader("Asset Ranking")

st.dataframe(
    ranking.round(4)
)

st.divider()

st.subheader("Macro Snapshot")

st.dataframe(
    latest[FEATURES]
)

st.divider()

st.subheader("Last 12 Regimes")

history = macro[
    ["date","cluster_name_final"]
].tail(12)

st.dataframe(history)
