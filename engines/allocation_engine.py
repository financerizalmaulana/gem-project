"""
Allocation Engine
=================
Produces a BUY / HOLD / REDUCE / AVOID call per tracked asset.

Design choice: this is a transparent, rule-based scoring system, NOT
a black-box ML classifier. With only 198 months of history (and as
few as 6 samples for the Crisis regime), training a model to output
recommendations directly would be overfitting dressed up as
sophistication. Instead this engine composes the outputs of the
engines that already have honest, inspectable statistics:

    score = w1 * (current-regime historical mean return, risk-adjusted)
          + w2 * (probability-weighted forward return over the chosen horizon,
                   using the transition matrix to blend in likely future regimes)

The weights and thresholds are named constants below — change them
in one place, not by hunting through logic.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ASSET_RETURN_COLUMNS
from engines.regime_engine import RegimeEngine
from engines.transition_engine import TransitionEngine
from engines.risk_engine import RiskEngine

# --- tunable thresholds (single source of truth for decision boundaries) ---
FORWARD_HORIZON = "3m"          # which transition horizon drives the forward blend
BUY_THRESHOLD = 1.5             # blended expected monthly return (%) above this -> BUY
REDUCE_THRESHOLD = -0.5         # below this -> REDUCE
AVOID_THRESHOLD = -2.0          # below this -> AVOID
RISK_ADJUST_VOL_PENALTY = 0.15  # subtract (volatility * this) from the raw score


class AllocationEngine:
    def __init__(self):
        self.regime_engine = RegimeEngine()
        self.transition_engine = TransitionEngine()
        self.risk_engine = RiskEngine()

    def _blended_forward_return(self, asset: str, forward_regime_probs: dict) -> float:
        """Probability-weighted expected monthly return across likely future regimes."""
        blended = 0.0
        for regime, prob_pct in forward_regime_probs.items():
            stats = self.risk_engine.asset_stats_by_regime(regime)["assets"].get(asset)
            if stats is None:
                continue
            blended += (prob_pct / 100.0) * stats["mean_monthly_return_pct"]
        return blended

    def recommend(self, asset: str) -> dict:
        current = self.regime_engine.detect_latest()
        current_regime = current["regime"]
        current_stats = self.risk_engine.asset_stats_by_regime(current_regime)["assets"].get(asset)
        forward_probs = self.transition_engine.forecast(current_regime)[FORWARD_HORIZON]
        blended_forward = self._blended_forward_return(asset, forward_probs)

        if current_stats is None:
            return {"asset": asset, "call": "NO DATA", "reason": "no historical return data for this asset/regime"}

        raw_score = 0.5 * current_stats["mean_monthly_return_pct"] + 0.5 * blended_forward
        risk_adjusted_score = raw_score - RISK_ADJUST_VOL_PENALTY * current_stats["volatility_pct"]

        if risk_adjusted_score >= BUY_THRESHOLD:
            call = "BUY"
        elif risk_adjusted_score >= REDUCE_THRESHOLD:
            call = "HOLD"
        elif risk_adjusted_score >= AVOID_THRESHOLD:
            call = "REDUCE"
        else:
            call = "AVOID"

        return {
            "asset": asset,
            "call": call,
            "current_regime": current_regime,
            "regime_confidence": current["confidence_score"],
            "current_regime_mean_monthly_return_pct": current_stats["mean_monthly_return_pct"],
            f"blended_{FORWARD_HORIZON}_forward_return_pct": round(blended_forward, 2),
            "volatility_pct": current_stats["volatility_pct"],
            "risk_adjusted_score": round(risk_adjusted_score, 2),
            "historical_sample_size": current_stats["n_samples"],
            "caveat": (
                "Low sample size — directional signal only, not a precise estimate."
                if current_stats["n_samples"] < 20 else None
            ),
        }

    def recommend_all(self) -> dict:
        return {asset: self.recommend(asset) for asset in ASSET_RETURN_COLUMNS}


if __name__ == "__main__":
    import json
    engine = AllocationEngine()
    print(json.dumps(engine.recommend_all(), indent=2))
