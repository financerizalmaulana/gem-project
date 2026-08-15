# GEM AI Analyst Report — 2026-08-15

**Data as of:** 2026-06-30

## 1. Current Economic Regime
- **Regime:** Growth Risk-On
- **Confidence:** 59.0/100
- **Full probability distribution:** Growth Risk-On 37.81%, Disinflation Normal 28.81%, Inflation Shock 24.54%, Crisis 8.83%
- **Historical risk level of this regime:** 42.6/100 (avg volatility 7.77%/mo, 38.6% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Growth Risk-On 95.5%, Inflation Shock 3.6%, Disinflation Normal 0.9%, Crisis 0.0%
- **3m:** Growth Risk-On 88.2%, Inflation Shock 9.5%, Disinflation Normal 2.1%, Crisis 0.2%
- **6m:** Growth Risk-On 80.0%, Inflation Shock 16.0%, Disinflation Normal 3.2%, Crisis 0.7%
- **12m:** Growth Risk-On 70.4%, Inflation Shock 23.6%, Disinflation Normal 3.7%, Crisis 2.2%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **HOLD** | 3.77% | 3.39% | 20.3% | 0.54 |
| QQQ | **HOLD** | 1.83% | 1.71% | 4.96% | 1.03 |
| SPY | **HOLD** | 1.34% | 1.28% | 4.06% | 0.7 |
| GLD | **HOLD** | 2.21% | 1.95% | 5.94% | 1.19 |
| TLT | **HOLD** | 0.76% | 0.59% | 3.61% | 0.14 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -27.8% | -8.7% | 1.8% | 11.1% | 38.3% | 54.2% |
| 2m | -32.5% | -11.7% | 3.6% | 23.1% | 61.1% | 54.6% |
| 3m | -37.4% | -14.2% | 5.6% | 32.0% | 78.7% | 57.5% |
| 6m | -47.7% | -18.3% | 11.1% | 52.6% | 138.7% | 59.1% |
| 12m | -62.4% | -25.5% | 17.9% | 84.1% | 264.4% | 59.4% |
| 2y | -76.6% | -34.6% | 30.3% | 154.9% | 566.1% | 60.0% |
| 3y | -82.8% | -40.8% | 41.0% | 227.1% | 1007.5% | 60.3% |
| 4y | -86.9% | -43.4% | 53.7% | 320.9% | 1516.7% | 61.5% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -10.7% | 20.6% | 61.2% | 1.9% | 107.5% | 340.9% |
| SPY | -9.8% | 15.5% | 45.1% | 2.1% | 74.4% | 200.9% |
| GLD | -12.4% | 21.9% | 69.4% | -1.5% | 101.9% | 320.8% |
| TLT | -15.4% | 5.5% | 32.1% | -35.2% | 14.7% | 88.0% |

## 5. Active Warnings
- **[HIGH]** master_dataset.parquet's latest row is 2026-06-30 (46 days old). Every other check below is computed from this same stale data — the data ingestion pipeline (data/fetch_macro_data.py) may be failing silently.

## 6. Indonesia Macro Layer
- Inflation: 1.95% YoY (contained)
- BI rate proxy: 5.88% (hiking)
- USD/IDR: 17534.0 (weakening over 3m)
- Trade balance: narrowing surplus
  - ⚠️ bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate
  - ⚠️ usdidr is quarterly data forward-filled to monthly — not a real monthly read
  - ⚠️ This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)

---
*Generated automatically. Every number above traces back to a specific engine — see the corresponding module for methodology and caveats. This is a decision-support tool, not financial advice.*