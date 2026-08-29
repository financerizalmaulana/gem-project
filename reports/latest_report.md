# GEM AI Analyst Report — 2026-08-29

**Data as of:** 2026-07-31

## 1. Current Economic Regime
- **Regime:** Growth Risk-On
- **Confidence:** 61.4/100
- **Full probability distribution:** Growth Risk-On 37.86%, Disinflation Normal 26.5%, Inflation Shock 26.39%, Crisis 9.24%
- **Historical risk level of this regime:** 42.4/100 (avg volatility 7.71%/mo, 38.6% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Growth Risk-On 95.5%, Inflation Shock 3.6%, Disinflation Normal 0.9%, Crisis 0.0%
- **3m:** Growth Risk-On 88.2%, Inflation Shock 9.5%, Disinflation Normal 2.1%, Crisis 0.2%
- **6m:** Growth Risk-On 80.0%, Inflation Shock 16.0%, Disinflation Normal 3.2%, Crisis 0.7%
- **12m:** Growth Risk-On 70.4%, Inflation Shock 23.6%, Disinflation Normal 3.7%, Crisis 2.2%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **HOLD** | 3.9% | 3.51% | 19.93% | 0.71 |
| QQQ | **HOLD** | 1.63% | 1.54% | 5.07% | 0.82 |
| SPY | **HOLD** | 1.31% | 1.26% | 4.02% | 0.68 |
| GLD | **HOLD** | 2.17% | 1.92% | 5.87% | 1.16 |
| TLT | **HOLD** | 0.63% | 0.48% | 3.65% | 0.01 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -27.8% | -8.7% | 1.8% | 10.9% | 38.3% | 55.8% |
| 2m | -32.1% | -11.6% | 3.7% | 21.7% | 60.9% | 54.9% |
| 3m | -37.3% | -14.0% | 5.7% | 30.5% | 77.6% | 57.5% |
| 6m | -46.7% | -17.6% | 11.1% | 49.5% | 134.3% | 59.6% |
| 12m | -61.4% | -22.7% | 19.1% | 87.3% | 262.1% | 60.5% |
| 2y | -75.7% | -30.8% | 32.0% | 163.6% | 576.7% | 61.9% |
| 3y | -81.5% | -37.5% | 50.3% | 243.4% | 1019.1% | 62.5% |
| 4y | -85.1% | -40.5% | 62.7% | 331.7% | 1606.1% | 62.9% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -11.4% | 17.8% | 59.0% | -5.5% | 92.6% | 320.2% |
| SPY | -9.3% | 14.6% | 44.7% | 0.9% | 72.6% | 195.2% |
| GLD | -12.7% | 21.4% | 68.6% | -2.2% | 99.8% | 315.1% |
| TLT | -16.1% | 4.0% | 30.2% | -36.3% | 10.3% | 79.7% |

## 5. Active Warnings
- No warnings triggered this run.

## 6. Indonesia Macro Layer
- Inflation: 1.95% YoY (contained)
- BI rate proxy: 5.88% (hiking)
- USD/IDR: 17534.0 (weakening over 3m)
- Trade balance: deficit
  - ⚠️ bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate
  - ⚠️ usdidr is quarterly data forward-filled to monthly — not a real monthly read
  - ⚠️ This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)

---
*Generated automatically. Every number above traces back to a specific engine — see the corresponding module for methodology and caveats. This is a decision-support tool, not financial advice.*