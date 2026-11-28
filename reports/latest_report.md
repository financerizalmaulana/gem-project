# GEM AI Analyst Report — 2026-11-28

**Data as of:** 2026-10-31

## 1. Current Economic Regime
- **Regime:** Inflation Shock
- **Confidence:** 58.2/100
- **Full probability distribution:** Inflation Shock 36.03%, Growth Risk-On 27.84%, Disinflation Normal 24.69%, Crisis 11.44%
- **Historical risk level of this regime:** 50.6/100 (avg volatility 8.0%/mo, 53.1% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Inflation Shock 92.7%, Growth Risk-On 5.5%, Crisis 1.8%, Disinflation Normal 0.0%
- **3m:** Inflation Shock 80.3%, Growth Risk-On 14.9%, Crisis 4.6%, Disinflation Normal 0.1%
- **6m:** Inflation Shock 65.9%, Growth Risk-On 26.2%, Crisis 7.3%, Disinflation Normal 0.5%
- **12m:** Inflation Shock 47.9%, Growth Risk-On 41.3%, Crisis 9.4%, Disinflation Normal 1.4%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **AVOID** | -1.59% | -0.38% | 19.61% | -3.93 |
| QQQ | **HOLD** | 0.31% | 0.82% | 6.72% | -0.44 |
| SPY | **HOLD** | 0.68% | 0.9% | 5.27% | -0.0 |
| GLD | **REDUCE** | -0.31% | 0.26% | 4.0% | -0.63 |
| TLT | **REDUCE** | -0.67% | -0.38% | 4.41% | -1.19 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -35.4% | -15.7% | -6.1% | 12.2% | 39.8% | 38.2% |
| 2m | -41.6% | -21.6% | -6.2% | 13.6% | 47.7% | 40.5% |
| 3m | -48.4% | -27.0% | -8.3% | 15.2% | 58.7% | 39.8% |
| 6m | -61.7% | -37.5% | -14.3% | 19.5% | 89.8% | 37.8% |
| 12m | -75.4% | -50.7% | -19.0% | 32.7% | 168.9% | 38.9% |
| 2y | -85.1% | -60.4% | -18.9% | 69.5% | 377.4% | 42.3% |
| 3y | -90.2% | -64.8% | -12.3% | 110.0% | 726.3% | 46.0% |
| 4y | -92.3% | -65.2% | -7.8% | 171.0% | 1115.0% | 47.9% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -26.3% | 9.4% | 68.9% | -18.6% | 83.6% | 416.8% |
| SPY | -18.1% | 10.5% | 50.1% | -7.8% | 64.8% | 217.0% |
| GLD | -21.0% | 2.4% | 45.6% | -23.8% | 62.4% | 273.2% |
| TLT | -26.5% | -3.8% | 24.1% | -40.5% | 4.3% | 71.4% |

## 5. Active Warnings
- **[HIGH]** BTC: AVOID (risk-adjusted score -3.93)
- **[MEDIUM]** GLD: REDUCE (risk-adjusted score -0.63)
- **[MEDIUM]** TLT: REDUCE (risk-adjusted score -1.19)

## 6. Indonesia Macro Layer
- Inflation: nan% YoY (contained)
- BI rate proxy: 5.17% (cutting)
- USD/IDR: 17865.0 (weakening over 3m)
- Trade balance: widening surplus
  - ⚠️ bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate
  - ⚠️ usdidr is quarterly data forward-filled to monthly — not a real monthly read
  - ⚠️ This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)

---
*Generated automatically. Every number above traces back to a specific engine — see the corresponding module for methodology and caveats. This is a decision-support tool, not financial advice.*