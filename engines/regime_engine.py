"""
Regime Engine
=============
Single responsibility: given the latest macro feature row, determine
which economic regime we are in right now, with a probability
distribution over all regimes and a confidence score.

This replaces the inline regime-detection code that used to live
directly inside dashboard.py. Centralizing it here means the
dashboard, the allocation engine, the alert engine, and the report
generator all get the SAME answer, computed the SAME way — the
previous project's core bug (dashboard using one cluster-id space,
asset ranking using another) is structurally impossible here because
everything downstream consumes `regime_name`, never a raw cluster id.
"""

import json
import joblib
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, MACRO_FEATURES


class RegimeEngine:
    def __init__(self):
        self.scaler = joblib.load(PATHS["scaler"])
        self.kmeans = joblib.load(PATHS["kmeans"])
        with open(PATHS["regime_map"]) as f:
            self.regime_map = {int(k): v for k, v in json.load(f).items()}

    def detect(self, feature_row: pd.Series) -> dict:
        """
        feature_row: a pandas Series containing at least MACRO_FEATURES.
        Returns a dict with the current regime, full probability
        distribution, and a confidence score (0-100).
        """
        X = feature_row[MACRO_FEATURES].to_frame().T
        X_scaled = self.scaler.transform(X)
        dist = cdist(X_scaled, self.kmeans.cluster_centers_, metric="euclidean")[0]

        inv = 1.0 / np.maximum(dist, 1e-9)
        prob = inv / inv.sum() * 100

        pred_cluster = int(np.argmin(dist))
        regime_name = self.regime_map[pred_cluster]

        prob_by_regime = {
            self.regime_map[i]: round(float(prob[i]), 2)
            for i in range(len(dist))
        }
        sorted_probs = dict(sorted(prob_by_regime.items(), key=lambda kv: kv[1], reverse=True))

        # Confidence: gap between top probability and second-best.
        # A wide gap (e.g. 70% vs 15%) means the model is confident.
        # A narrow gap (e.g. 40% vs 35%) means we're near a regime boundary.
        sorted_vals = sorted(prob, reverse=True)
        margin = sorted_vals[0] - sorted_vals[1]
        confidence = float(np.clip(50 + margin, 0, 100))  # heuristic: base 50 + margin

        return {
            "regime": regime_name,
            "cluster_id": pred_cluster,
            "probabilities": sorted_probs,
            "top_probability": sorted_probs[regime_name],
            "confidence_score": round(confidence, 1),
            "distances": {self.regime_map[i]: round(float(dist[i]), 3) for i in range(len(dist))},
        }

    def detect_latest(self) -> dict:
        master = pd.read_parquet(PATHS["master_dataset"])
        latest = master.iloc[-1]
        result = self.detect(latest)
        result["date"] = str(latest["date"].date()) if hasattr(latest["date"], "date") else str(latest["date"])
        return result

    def regime_history(self, n_months: int = 12) -> pd.DataFrame:
        master = pd.read_parquet(PATHS["master_dataset"])
        return master[["date", "regime"]].tail(n_months).reset_index(drop=True)


if __name__ == "__main__":
    engine = RegimeEngine()
    result = engine.detect_latest()
    print(json.dumps(result, indent=2))
