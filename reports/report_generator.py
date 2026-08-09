"""
Report Generator (the "AI Analyst" output)
=============================================
Pulls together regime_engine + transition_engine + risk_engine +
allocation_engine + btc_forecast_engine + alert_engine into one
narrative markdown report — the automated version of goal statement
"memberikan informasi auto tentang potensi dan resiko" instead of
having to read four separate dashboard panels yourself.

This is deliberately template-based (not LLM-generated prose) so the
numbers in the report are always exactly what the engines computed —
no risk of a language model quietly rounding, inventing, or
misreporting a number in the process of writing nice sentences.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ASSET_RETURN_COLUMNS
from engines.regime_engine import RegimeEngine
from engines.transition_engine import TransitionEngine
from engines.risk_engine import RiskEngine
from engines.allocation_engine import AllocationEngine, FORWARD_HORIZON
from engines.btc_forecast_engine import BTCForecastEngine
from engines.alert_engine import AlertEngine


def generate_report() -> str:
    regime_engine = RegimeEngine()
    transition_engine = TransitionEngine()
    risk_engine = RiskEngine()
    allocation_engine = AllocationEngine()
    alert_engine = AlertEngine()

    current = regime_engine.detect_latest()
    transition_forecast = transition_engine.forecast(current["regime"])
    regime_risk = risk_engine.regime_risk_score(current["regime"])
    allocations = allocation_engine.recommend_all()
    alerts = alert_engine.run_all_checks()
    # BTCForecastEngine is asset-generic (asset_col param) — reused for every
    # tracked asset here rather than writing a parallel per-asset engine.
    multi_asset_forecast = {
        asset: BTCForecastEngine(asset_col=col).forecast(current["regime"])
        for asset, col in ASSET_RETURN_COLUMNS.items()
    }
    btc_forecast = multi_asset_forecast["BTC"]

    lines = []
    lines.append(f"# GEM AI Analyst Report — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Data as of:** {current['date']}")
    lines.append("")

    lines.append("## 1. Current Economic Regime")
    lines.append(f"- **Regime:** {current['regime']}")
    lines.append(f"- **Confidence:** {current['confidence_score']}/100")
    lines.append(f"- **Full probability distribution:** " +
                 ", ".join(f"{k} {v}%" for k, v in current["probabilities"].items()))
    lines.append(f"- **Historical risk level of this regime:** {regime_risk['risk_score']}/100 "
                 f"(avg volatility {regime_risk['avg_volatility_pct']}%/mo, "
                 f"{regime_risk['avg_negative_month_rate_pct']}% of months negative across tracked assets, "
                 f"sample confidence: {regime_risk['sample_confidence']})")
    lines.append("")

    lines.append("## 2. Regime Transition Forecast (forward-looking risk)")
    for horizon, probs in transition_forecast.items():
        top = ", ".join(f"{k} {v}%" for k, v in probs.items())
        lines.append(f"- **{horizon}:** {top}")
    lines.append("")

    lines.append("## 3. Asset Recommendations")
    lines.append(f"*(blend of current-regime history + {FORWARD_HORIZON} forward transition-weighted return, risk-adjusted for volatility)*")
    lines.append("")
    lines.append("| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |")
    lines.append("|---|---|---|---|---|---|")
    for asset, rec in allocations.items():
        if rec.get("call") == "NO DATA":
            continue
        lines.append(f"| {asset} | **{rec['call']}** | {rec['current_regime_mean_monthly_return_pct']}% | "
                     f"{rec[f'blended_{FORWARD_HORIZON}_forward_return_pct']}% | {rec['volatility_pct']}% | "
                     f"{rec['risk_adjusted_score']} |")
        if rec.get("caveat"):
            lines.append(f"  - ⚠️ {asset}: {rec['caveat']}")
    lines.append("")

    lines.append("## 4. BTC Multi-Horizon Scenario Ranges")
    lines.append("*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*")
    lines.append("")
    lines.append("| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |")
    lines.append("|---|---|---|---|---|---|---|")
    for h, data in btc_forecast.items():
        p = data["cumulative_return_pct_percentiles"]
        lines.append(f"| {h} | {p['p5']}% | {p['p25']}% | {p['p50']}% | {p['p75']}% | {p['p95']}% | "
                     f"{data['prob_positive_pct']}% |")
    lines.append("")

    lines.append("## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges")
    lines.append("*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "
                 "\"multi-horizon forecasting is BTC-only\" gap using the same engine, not a new one)*")
    lines.append("")
    lines.append("| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |")
    lines.append("|---|---|---|---|---|---|---|")
    for asset, forecast in multi_asset_forecast.items():
        if asset == "BTC":
            continue
        p12 = forecast["12m"]["cumulative_return_pct_percentiles"]
        p4y = forecast["4y"]["cumulative_return_pct_percentiles"]
        lines.append(f"| {asset} | {p12['p5']}% | {p12['p50']}% | {p12['p95']}% | "
                     f"{p4y['p5']}% | {p4y['p50']}% | {p4y['p95']}% |")
    lines.append("")

    lines.append("## 5. Active Warnings")
    if alerts:
        for a in alerts:
            lines.append(f"- **[{a['severity'].upper()}]** {a['message']}")
    else:
        lines.append("- No warnings triggered this run.")
    lines.append("")

    lines.append("## 6. Indonesia Macro Layer")
    id_api_key = os.environ.get("FRED_API_KEY")
    if not id_api_key:
        lines.append("- Data source connected (`engines/indonesia_macro_engine.py`) but not run here — "
                     "no FRED_API_KEY set. Rule-based directional read (inflation/rate/IDR trend), "
                     "not a validated regime classification like the global engine.")
    else:
        try:
            from engines.indonesia_macro_engine import IndonesiaMacroEngine
            id_engine = IndonesiaMacroEngine()
            id_raw = id_engine.fetch_raw(id_api_key)
            id_assessment = id_engine.assess(id_raw)
            lines.append(f"- Inflation: {id_assessment['id_cpi_yoy_pct']}% YoY ({id_assessment['inflation_read']})")
            lines.append(f"- BI rate proxy: {id_assessment['bi_rate_proxy_pct']}% ({id_assessment['policy_stance']})")
            lines.append(f"- USD/IDR: {id_assessment['usdidr_level']} ({id_assessment['idr_direction_3m']} over 3m)")
            lines.append(f"- Trade balance: {id_assessment['trade_balance_read']}")
            for c in id_assessment["caveats"]:
                lines.append(f"  - ⚠️ {c}")
        except Exception as e:
            lines.append(f"- Data fetch failed: {e} — see `engines/indonesia_macro_engine.py` for the untested-in-sandbox caveat.")
    lines.append("")

    lines.append("---")
    lines.append("*Generated automatically. Every number above traces back to a specific engine — "
                 "see the corresponding module for methodology and caveats. This is a decision-support "
                 "tool, not financial advice.*")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(report)
