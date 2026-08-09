"""
Risk Engine
===========
Computes regime-conditional risk statistics per asset: mean return,
volatility, win rate, worst month, and a sample-size-aware confidence
flag (the previous project's Crisis regime has only 6 historical
monthly observations — any statistic built on that should be labeled
low-confidence rather than presented with false precision).
"""

import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, ASSET_RETURN_COLUMNS


class RiskEngine:
    def __init__(self):
        self.master = pd.read_parquet(PATHS["master_dataset"])

    def asset_stats_by_regime(self, regime: str) -> dict:
        subset = self.master[self.master["regime"] == regime]
        n = len(subset)
        stats = {}
        for asset, col in ASSET_RETURN_COLUMNS.items():
            returns = subset[col].dropna()
            if len(returns) == 0:
                stats[asset] = None
                continue
            stats[asset] = {
                "mean_monthly_return_pct": round(float(returns.mean()) * 100, 2),
                "volatility_pct": round(float(returns.std()) * 100, 2),
                "win_rate_pct": round(float((returns > 0).mean()) * 100, 1),
                "worst_month_pct": round(float(returns.min()) * 100, 2),
                "best_month_pct": round(float(returns.max()) * 100, 2),
                "n_samples": int(len(returns)),
            }
        return {
            "regime": regime,
            "n_months_in_regime": n,
            "sample_confidence": self._confidence_label(n),
            "assets": stats,
        }

    @staticmethod
    def _confidence_label(n: int) -> str:
        if n >= 60:
            return "high (ample history)"
        if n >= 20:
            return "medium"
        return "low (small sample — treat as directional only, not precise)"

    def regime_risk_score(self, regime: str) -> dict:
        """
        A single 0-100 'how dangerous is this regime historically' score,
        based on average asset volatility and how often returns were
        negative across all tracked assets while in this regime.
        """
        stats = self.asset_stats_by_regime(regime)
        vols, neg_rates = [], []
        for a, s in stats["assets"].items():
            if s is None:
                continue
            vols.append(s["volatility_pct"])
            neg_rates.append(100 - s["win_rate_pct"])
        if not vols:
            return {"regime": regime, "risk_score": None, "note": "no data"}
        avg_vol = np.mean(vols)
        avg_neg_rate = np.mean(neg_rates)
        # simple weighted blend, capped 0-100
        score = float(np.clip(avg_vol * 3 + avg_neg_rate * 0.5, 0, 100))
        return {
            "regime": regime,
            "risk_score": round(score, 1),
            "avg_volatility_pct": round(avg_vol, 2),
            "avg_negative_month_rate_pct": round(avg_neg_rate, 1),
            "sample_confidence": stats["sample_confidence"],
        }


if __name__ == "__main__":
    import json
    engine = RiskEngine()
    print(json.dumps(engine.asset_stats_by_regime("Growth Risk-On"), indent=2))
    print()
    print(json.dumps(engine.regime_risk_score("Growth Risk-On"), indent=2))
    print()
    print(json.dumps(engine.regime_risk_score("Crisis"), indent=2))
