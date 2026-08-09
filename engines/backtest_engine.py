"""
Backtest Engine
================
Answers two honest questions the audit flagged as unvalidated:
  1. Did the allocation engine's BUY/HOLD/REDUCE/AVOID calls actually
     correspond to better/worse forward returns historically?
  2. Is the BTC forecast engine's percentile band actually calibrated —
     i.e. does the realized return fall inside the p5-p95 band roughly
     90% of the time, like it should if the band means what it claims?

METHODOLOGY NOTE — read before trusting these numbers:
This is a WALK-FORWARD backtest: at each historical month t, only data
strictly before t is used to compute regime-conditional statistics
(no look-ahead) for the current-regime-mean term. This version now
ALSO includes the transition-matrix-blended forward-return term (the
other half of the live allocation_engine's score) — a gap noted here
in an earlier version of this module. One honest limitation remains,
and is now the more important one to be aware of: the transition
matrix itself (models/transition_matrices/) is a single static summary
built once from the FULL dataset, used identically here and in
production — it was never recomputed point-in-time per month anywhere
in this codebase. That means the transition-blended term in this
backtest (and in live production) technically has access to
regime-transition patterns from AFTER date t, a form of look-ahead
bias shared by the backtest and the system it's validating, not
introduced by the backtest alone. Rebuilding a point-in-time
transition matrix at every historical step is future work, not done
here (see docs/CHANGELOG.md).

With only ~198 months of history and 4 regimes (Crisis has 6 samples
total), any backtest slice will have very few independent observations
per regime — treat results directionally, not as statistically
significant proof.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PATHS, ASSET_RETURN_COLUMNS
from engines.allocation_engine import RISK_ADJUST_VOL_PENALTY, BUY_THRESHOLD, REDUCE_THRESHOLD, AVOID_THRESHOLD, FORWARD_HORIZON


def _classify(score: float, buy_th: float = BUY_THRESHOLD, reduce_th: float = REDUCE_THRESHOLD,
              avoid_th: float = AVOID_THRESHOLD) -> str:
    """Same thresholds as allocation_engine.AllocationEngine.recommend — reused, not duplicated logic.
    Thresholds are parameters (not just module constants) so recalibration can be tested here first."""
    if score >= buy_th:
        return "BUY"
    if score >= reduce_th:
        return "HOLD"
    if score >= avoid_th:
        return "REDUCE"
    return "AVOID"


def _compute_full_scores(min_warmup_months: int = 36) -> pd.DataFrame:
    """
    Shared computation used by both backtest_allocation_calls (evaluates
    calls under current thresholds) and calibrate_allocation_thresholds
    (searches for better thresholds) — one score-computation path, not two.
    """
    master = pd.read_parquet(PATHS["master_dataset"])
    transition_matrix = pd.read_csv(
        os.path.join(PATHS["transition_matrix_dir"], f"transition_matrix_{FORWARD_HORIZON}.csv"), index_col=0
    )
    rows = []

    for t in range(min_warmup_months, len(master) - 1):
        history = master.iloc[:t]
        current_regime = master.iloc[t]["regime"]
        if current_regime not in transition_matrix.index:
            continue
        forward_probs = transition_matrix.loc[current_regime]

        for asset, col in ASSET_RETURN_COLUMNS.items():
            regime_history = history.loc[history["regime"] == current_regime, col].dropna()
            if len(regime_history) < 5:
                continue  # not enough point-in-time history yet for this regime
            pit_mean_pct = regime_history.mean() * 100
            pit_vol_pct = regime_history.std() * 100

            blended_forward_pct = 0.0
            for regime, prob in forward_probs.items():
                fwd_hist = history.loc[history["regime"] == regime, col].dropna()
                if len(fwd_hist) == 0:
                    continue
                blended_forward_pct += float(prob) * fwd_hist.mean() * 100

            raw_score = 0.5 * pit_mean_pct + 0.5 * blended_forward_pct
            score = raw_score - RISK_ADJUST_VOL_PENALTY * pit_vol_pct

            realized_next_month = master.iloc[t + 1][col]
            if pd.isna(realized_next_month):
                continue

            rows.append({
                "date": master.iloc[t]["date"], "asset": asset, "score": score,
                "realized_next_month_return_pct": realized_next_month * 100,
            })

    return pd.DataFrame(rows)


def backtest_allocation_calls(min_warmup_months: int = 36) -> dict:
    """
    Walk-forward test of the FULL live allocation_engine score (current-
    regime mean + transition-blended forward term, risk-adjusted for
    volatility — identical formula to AllocationEngine.recommend). For
    each month t past the warmup period, computes what the call WOULD
    have been using only history strictly before t (see module
    docstring for the one remaining look-ahead caveat), then checks the
    asset's ACTUAL realized return in month t+1.
    """
    df = _compute_full_scores(min_warmup_months)
    if df.empty:
        return {"error": "no backtest rows produced — check warmup period vs. dataset length"}

    df["call"] = df["score"].apply(_classify)

    summary = (df.groupby("call")["realized_next_month_return_pct"]
                 .agg(["mean", "median", "count"])
                 .round(2)
                 .to_dict(orient="index"))

    call_order = ["BUY", "HOLD", "REDUCE", "AVOID"]
    means = [summary[c]["mean"] for c in call_order if c in summary]
    is_monotonic = all(means[i] >= means[i + 1] for i in range(len(means) - 1))

    return {
        "n_observations": len(df),
        "date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
        "summary_by_call": summary,
        "is_monotonically_ordered": is_monotonic,
        "note": ("BUY calls should show a higher mean forward return than AVOID calls if the "
                 "signal has any validity. Small per-bucket counts (see 'count') mean this is "
                 "directional evidence, not statistical proof. If is_monotonically_ordered is "
                 "False, see calibrate_allocation_thresholds() for a data-driven threshold fix."),
    }


def calibrate_allocation_thresholds(min_warmup_months: int = 36,
                                     quantiles: tuple = (0.75, 0.50, 0.25)) -> dict:
    """
    Recalibration, not just diagnosis: fixed magic-number thresholds
    (BUY_THRESHOLD=1.5, REDUCE_THRESHOLD=-0.5, AVOID_THRESHOLD=-2.0)
    were picked without reference to the actual score distribution,
    which is how the non-monotonic backtest result happened — the
    AVOID bucket could end up small and dominated by a few
    high-variance crisis-rebound months. This computes thresholds from
    the empirical score distribution's own quantiles instead (top 25%
    of scores -> BUY, next 25% -> HOLD, next 25% -> REDUCE, bottom 25%
    -> AVOID), which guarantees every bucket has a comparable sample
    size — the specific defect that caused AVOID's small-sample mean
    to swing higher than HOLD/REDUCE's in the fixed-threshold version.
    """
    df = _compute_full_scores(min_warmup_months)
    if df.empty:
        return {"error": "no backtest rows produced"}

    q_buy, q_hold, q_reduce = quantiles
    buy_th = float(df["score"].quantile(q_buy))
    reduce_th = float(df["score"].quantile(q_hold))
    avoid_th = float(df["score"].quantile(q_reduce))

    df["call"] = df["score"].apply(lambda s: _classify(s, buy_th, reduce_th, avoid_th))
    summary = (df.groupby("call")["realized_next_month_return_pct"]
                 .agg(["mean", "median", "count"])
                 .round(2)
                 .to_dict(orient="index"))
    call_order = ["BUY", "HOLD", "REDUCE", "AVOID"]
    means = [summary[c]["mean"] for c in call_order if c in summary]
    is_monotonic = all(means[i] >= means[i + 1] for i in range(len(means) - 1))

    return {
        "recalibrated_thresholds": {"BUY_THRESHOLD": round(buy_th, 3), "REDUCE_THRESHOLD": round(reduce_th, 3),
                                     "AVOID_THRESHOLD": round(avoid_th, 3)},
        "summary_by_call_with_new_thresholds": summary,
        "is_monotonically_ordered": is_monotonic,
        "n_observations": len(df),
    }


def backtest_btc_forecast_calibration(horizons=("3m", "12m"), min_warmup_months: int = 36,
                                       n_simulations: int = 500) -> dict:
    """
    Calibration/coverage test: for each historical starting point,
    simulate the p5-p95 band using only prior data, then check whether
    BTC's ACTUAL realized cumulative return over that horizon fell
    inside the band. A well-calibrated 90% interval should contain the
    outcome ~90% of the time across many starting points.
    """
    from engines.btc_forecast_engine import HORIZONS_MONTHS

    master = pd.read_parquet(PATHS["master_dataset"])
    rng = np.random.default_rng(7)
    transition_1m = pd.read_csv(
        os.path.join(PATHS["transition_matrix_dir"], "transition_matrix_1m.csv"), index_col=0
    )  # NOTE: full-sample transition matrix reused at every backtest point — see module docstring

    results = {h: {"covered": 0, "total": 0} for h in horizons}

    for t in range(min_warmup_months, len(master)):
        history = master.iloc[:t]
        start_regime = master.iloc[t - 1]["regime"] if t > 0 else master.iloc[0]["regime"]
        regime_returns = {
            regime: history.loc[history["regime"] == regime, "btc_ret"].dropna().values
            for regime in transition_1m.index
        }
        if any(len(v) == 0 for v in regime_returns.values()):
            continue  # not enough point-in-time history across all regimes yet

        for h in horizons:
            n_months = HORIZONS_MONTHS[h]
            if t + n_months >= len(master):
                continue
            actual_prices = master.iloc[t:t + n_months + 1]["btc_ret"].dropna()
            if len(actual_prices) < n_months:
                continue
            actual_cum_return = (1 + master.iloc[t + 1:t + n_months + 1]["btc_ret"]).prod() - 1
            if pd.isna(actual_cum_return):
                continue

            sims = np.empty(n_simulations)
            for i in range(n_simulations):
                regime = start_regime
                cum = 1.0
                for _ in range(n_months):
                    pool = regime_returns.get(regime)
                    r = rng.choice(pool)
                    cum *= (1 + r)
                    probs = transition_1m.loc[regime].values
                    probs = probs / probs.sum()
                    regime = rng.choice(transition_1m.columns, p=probs)
                sims[i] = cum - 1.0

            p5, p95 = np.percentile(sims, [5, 95])
            covered = p5 <= actual_cum_return <= p95
            results[h]["covered"] += int(covered)
            results[h]["total"] += 1

    out = {}
    for h, r in results.items():
        out[h] = {
            "coverage_pct": round(100 * r["covered"] / r["total"], 1) if r["total"] > 0 else None,
            "target_pct": 90.0,
            "n_test_points": r["total"],
        }
    out["note"] = ("coverage_pct close to 90% means the p5-p95 band is well-calibrated. "
                    "Far below 90% means the band is too narrow (overconfident); far above "
                    "means too wide. Reuses the full-sample transition matrix at every "
                    "historical point (see module docstring) — a genuine look-ahead "
                    "limitation, not a hidden one.")
    return out


if __name__ == "__main__":
    import json
    print("=== Allocation call backtest ===")
    print(json.dumps(backtest_allocation_calls(), indent=2, default=str))
    print()
    print("=== BTC forecast calibration backtest (this takes a minute) ===")
    print(json.dumps(backtest_btc_forecast_calibration(), indent=2, default=str))
