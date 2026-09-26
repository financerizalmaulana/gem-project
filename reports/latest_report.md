# GEM AI Analyst Report — 2026-09-26

**Data as of:** 2026-08-31

## 1. Current Economic Regime
- **Regime:** Growth Risk-On
- **Confidence:** 57.6/100
- **Full probability distribution:** Growth Risk-On 35.62%, Inflation Shock 28.01%, Disinflation Normal 26.9%, Crisis 9.48%
- **Historical risk level of this regime:** 42.1/100 (avg volatility 7.76%/mo, 37.6% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Growth Risk-On 95.5%, Inflation Shock 3.6%, Disinflation Normal 0.9%, Crisis 0.0%
- **3m:** Growth Risk-On 88.2%, Inflation Shock 9.5%, Disinflation Normal 2.1%, Crisis 0.2%
- **6m:** Growth Risk-On 80.0%, Inflation Shock 16.0%, Disinflation Normal 3.2%, Crisis 0.7%
- **12m:** Growth Risk-On 70.4%, Inflation Shock 23.6%, Disinflation Normal 3.7%, Crisis 2.2%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **HOLD** | 4.53% | 4.06% | 20.32% | 1.25 |
| QQQ | **HOLD** | 1.88% | 1.76% | 4.92% | 1.08 |
| SPY | **HOLD** | 1.37% | 1.31% | 4.02% | 0.74 |
| GLD | **HOLD** | 2.39% | 2.11% | 5.99% | 1.35 |
| TLT | **HOLD** | 0.76% | 0.59% | 3.56% | 0.14 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -27.8% | -8.7% | 1.8% | 11.1% | 38.3% | 55.8% |
| 2m | -32.1% | -11.4% | 4.6% | 25.2% | 65.7% | 56.4% |
| 3m | -37.2% | -12.9% | 7.3% | 34.6% | 83.6% | 59.3% |
| 6m | -46.2% | -15.5% | 14.7% | 55.9% | 144.8% | 61.8% |
| 12m | -60.0% | -19.5% | 25.5% | 100.6% | 287.8% | 63.7% |
| 2y | -74.4% | -24.9% | 46.2% | 192.1% | 664.0% | 65.3% |
| 3y | -80.3% | -29.7% | 70.1% | 306.3% | 1238.2% | 66.4% |
| 4y | -83.5% | -30.3% | 94.8% | 421.4% | 2065.8% | 67.0% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -9.1% | 20.8% | 62.2% | 1.6% | 110.6% | 347.4% |
| SPY | -8.8% | 15.4% | 45.4% | 2.9% | 76.6% | 201.7% |
| GLD | -11.6% | 23.7% | 72.6% | 1.4% | 113.8% | 352.4% |
| TLT | -15.1% | 5.5% | 31.3% | -35.2% | 15.5% | 87.5% |

## 5. Active Warnings
- No warnings triggered this run.

## 6. Indonesia Macro Layer
- Inflation: 1.95% YoY (contained)
- BI rate proxy: 6.06% (hiking)
- USD/IDR: 17534.0 (weakening over 3m)
- Trade balance: deficit
  - ⚠️ bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate
  - ⚠️ usdidr is quarterly data forward-filled to monthly — not a real monthly read
  - ⚠️ This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)

---
*Generated automatically. Every number above traces back to a specific engine — see the corresponding module for methodology and caveats. This is a decision-support tool, not financial advice.*