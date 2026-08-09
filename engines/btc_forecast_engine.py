"""
BTC Forecast Engine
====================
Projects BTC price scenarios across 1, 3, 6, 12, 24, 36, 48 months.

GENERALIZATION NOTE: despite the name (kept for backward compatibility
— report_generator.py, dashboard/app.py, and backtest_engine.py all
import BTCForecastEngine directly), the class was already asset-generic
from its first version: `asset_col` defaults to "btc_ret" but accepts
any column in config.ASSET_RETURN_COLUMNS (e.g. BTCForecastEngine(
asset_col="gld_ret") forecasts Gold using the identical methodology).
This closes the "2-4 year forecasting is BTC-only" gap without adding
a parallel engine — report_generator.py and dashboard/app.py now loop
over every tracked asset using this same class.

IMPORTANT — methodology and honesty disclaimer:
This is NOT a price prediction model and does not claim to know the
future. It is a regime-switching Monte Carlo bootstrap:

  1. Starting from the current regime, simulate a monthly regime path
     forward using the 1-month transition matrix (a Markov chain).
  2. At each simulated month, draw a real historical monthly return
     AT RANDOM from the months that were actually in that regime
     (bootstrap resampling — no synthetic numbers).
  3. Compound the drawn returns across the path to get one possible
     cumulative outcome.
  4. Repeat thousands of times to build a distribution of outcomes,
     then report percentiles.

This produces a wide, honest range of scenarios grounded in actual
history, rather than a single confident-looking number. The tails
(5th/95th percentile) will be genuinely wide — that width IS the
signal, and should not be papered over. With ~12 years of monthly
data (some regimes as few as ~6-28 samples, and thinner still for
assets with a shorter price history than BTC), longer horizons
(2-4 years) compound a lot of sampling uncertainty; treat those as
directional scenario ranges, not forecasts.
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS

HORIZONS_MONTHS = {"1m": 1, "2m": 2, "3m": 3, "6m": 6, "12m": 12, "2y": 24, "3y": 36, "4y": 48}
N_SIMULATIONS = 5000
PERCENTILES = [5, 25, 50, 75, 95]


class BTCForecastEngine:
    def __init__(self, asset_col: str = "btc_ret", seed: int = 42):
        self.master = pd.read_parquet(PATHS["master_dataset"])
        self.asset_col = asset_col
        self.transition_1m = pd.read_csv(
            os.path.join(PATHS["transition_matrix_dir"], "transition_matrix_1m.csv"), index_col=0
        )
        self.regime_returns = {
            regime: self.master.loc[self.master["regime"] == regime, asset_col].dropna().values
            for regime in self.transition_1m.index
        }
        self.rng = np.random.default_rng(seed)

    def _simulate_all_paths(self, start_regime: str, n_months: int, n_sims: int) -> np.ndarray:
        """
        Vectorized across n_sims simulations at once. Returns an array of
        shape (n_sims, n_months) of cumulative-return-to-date, so every
        horizon checkpoint can be read off a single simulation run instead
        of resimulating from scratch per horizon.
        """
        regimes = np.array(self.transition_1m.columns)
        regime_idx = {r: i for i, r in enumerate(regimes)}
        trans_matrix = self.transition_1m.loc[regimes, regimes].values  # rows sum to 1
        trans_matrix = trans_matrix / trans_matrix.sum(axis=1, keepdims=True)

        current_regime_idx = np.full(n_sims, regime_idx[start_regime])
        cumulative = np.ones(n_sims)
        path = np.empty((n_sims, n_months))

        for month in range(n_months):
            draws = np.empty(n_sims)
            for r_idx, r_name in enumerate(regimes):
                mask = current_regime_idx == r_idx
                k = mask.sum()
                if k == 0:
                    continue
                pool = self.regime_returns.get(r_name)
                if pool is None or len(pool) == 0:
                    pool = np.concatenate(list(self.regime_returns.values()))
                draws[mask] = self.rng.choice(pool, size=k, replace=True)
            cumulative *= (1 + draws)
            path[:, month] = cumulative - 1.0

            # advance regime for every simulation according to its row of the transition matrix
            new_idx = np.empty(n_sims, dtype=int)
            for r_idx, r_name in enumerate(regimes):
                mask = current_regime_idx == r_idx
                k = mask.sum()
                if k == 0:
                    continue
                new_idx[mask] = self.rng.choice(len(regimes), size=k, p=trans_matrix[r_idx])
            current_regime_idx = new_idx

        return path

    def forecast(self, start_regime: str) -> dict:
        max_months = max(HORIZONS_MONTHS.values())
        path = self._simulate_all_paths(start_regime, max_months, N_SIMULATIONS)

        out = {}
        for label, n_months in HORIZONS_MONTHS.items():
            sims = path[:, n_months - 1]
            pct = {f"p{p}": round(float(np.percentile(sims, p)) * 100, 1) for p in PERCENTILES}
            out[label] = {
                "months": n_months,
                "cumulative_return_pct_percentiles": pct,
                "prob_positive_pct": round(float((sims > 0).mean()) * 100, 1),
                "prob_loss_over_30pct": round(float((sims < -0.30).mean()) * 100, 1),
            }
        return out

    def sample_sizes(self) -> dict:
        return {regime: len(vals) for regime, vals in self.regime_returns.items()}


if __name__ == "__main__":
    import json
    from engines.regime_engine import RegimeEngine

    current = RegimeEngine().detect_latest()
    print(f"Simulating from current regime: {current['regime']} (as of {current['date']})")
    print(f"Historical sample sizes per regime for BTC: {BTCForecastEngine().sample_sizes()}")
    print()
    engine = BTCForecastEngine()
    result = engine.forecast(current["regime"])
    print(json.dumps(result, indent=2))
