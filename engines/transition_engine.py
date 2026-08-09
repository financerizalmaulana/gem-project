"""
Transition Engine
==================
Answers: "given the current regime, what's the probability of being
in each regime 1/3/6/12 months from now?"

This data (models/transition_matrices/*.csv) already existed in the
legacy export but was never connected to anything — it just sat in a
folder. This is the most direct implementation of the user's goal #4
("potensi & risiko 6bln/1thn ke depan") and part of goal #7 (warnings
about upcoming regime change): a rising probability of "Crisis" or
"Inflation Shock" a few months out from any given month IS the
early-warning signal.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, TRANSITION_HORIZONS


class TransitionEngine:
    def __init__(self):
        self.matrices = {}
        for h in TRANSITION_HORIZONS:
            path = os.path.join(PATHS["transition_matrix_dir"], f"transition_matrix_{h}.csv")
            df = pd.read_csv(path, index_col=0)
            self.matrices[h] = df

    def forecast(self, current_regime: str) -> dict:
        """Returns {horizon: {regime: probability}} for every configured horizon."""
        out = {}
        for h in TRANSITION_HORIZONS:
            m = self.matrices[h]
            if current_regime not in m.index:
                out[h] = None
                continue
            row = m.loc[current_regime].to_dict()
            out[h] = {k: round(float(v) * 100, 1) for k, v in sorted(row.items(), key=lambda kv: kv[1], reverse=True)}
        return out

    def risk_flags(self, current_regime: str, threshold: float = 25.0) -> list:
        """
        Flags any horizon where probability of moving into 'Crisis' or
        'Inflation Shock' exceeds `threshold` percent — a simple, explainable
        rule the alert_engine builds on.
        """
        forecast = self.forecast(current_regime)
        flags = []
        for h, probs in forecast.items():
            if probs is None:
                continue
            for adverse in ["Crisis", "Inflation Shock"]:
                p = probs.get(adverse, 0)
                if p >= threshold and adverse != current_regime:
                    flags.append({
                        "horizon": h,
                        "regime_at_risk": adverse,
                        "probability_pct": p,
                    })
        return flags


if __name__ == "__main__":
    import json
    engine = TransitionEngine()
    result = engine.forecast("Growth Risk-On")
    print(json.dumps(result, indent=2))
    print()
    print("Risk flags:", json.dumps(engine.risk_flags("Growth Risk-On"), indent=2))
