# GEM AI Analyst Report — 2026-10-29

**Data as of:** 2026-09-30

## 1. Current Economic Regime
- **Regime:** Inflation Shock
- **Confidence:** 57.8/100
- **Full probability distribution:** Inflation Shock 37.26%, Growth Risk-On 29.45%, Disinflation Normal 24.8%, Crisis 8.49%
- **Historical risk level of this regime:** 50.1/100 (avg volatility 7.97%/mo, 52.4% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Inflation Shock 92.7%, Growth Risk-On 5.5%, Crisis 1.8%, Disinflation Normal 0.0%
- **3m:** Inflation Shock 80.3%, Growth Risk-On 14.9%, Crisis 4.6%, Disinflation Normal 0.1%
- **6m:** Inflation Shock 65.9%, Growth Risk-On 26.2%, Crisis 7.3%, Disinflation Normal 0.5%
- **12m:** Inflation Shock 47.9%, Growth Risk-On 41.3%, Crisis 9.4%, Disinflation Normal 1.4%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **AVOID** | -1.12% | -0.0% | 19.63% | -3.51 |
| QQQ | **HOLD** | 0.65% | 1.09% | 6.6% | -0.12 |
| SPY | **HOLD** | 0.7% | 0.91% | 5.27% | 0.02 |
| GLD | **REDUCE** | -0.32% | 0.25% | 4.01% | -0.64 |
| TLT | **REDUCE** | -1.05% | -0.69% | 4.32% | -1.52 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -35.4% | -15.7% | -3.6% | 12.2% | 39.8% | 41.9% |
| 2m | -41.5% | -20.9% | -5.1% | 14.5% | 48.7% | 42.0% |
| 3m | -47.7% | -26.2% | -6.8% | 16.8% | 59.9% | 41.8% |
| 6m | -60.7% | -36.2% | -11.9% | 22.4% | 95.4% | 39.8% |
| 12m | -74.3% | -48.8% | -15.5% | 38.3% | 177.1% | 40.9% |
| 2y | -83.8% | -56.8% | -13.4% | 78.4% | 402.1% | 44.5% |
| 3y | -89.1% | -60.6% | -4.5% | 127.9% | 755.1% | 48.5% |
| 4y | -91.1% | -61.5% | 3.4% | 187.9% | 1185.0% | 50.8% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -23.4% | 12.7% | 71.9% | -8.9% | 95.8% | 436.0% |
| SPY | -18.1% | 10.7% | 50.2% | -7.5% | 65.4% | 219.3% |
| GLD | -21.1% | 2.3% | 45.6% | -24.0% | 62.2% | 273.2% |
| TLT | -28.7% | -7.4% | 20.5% | -47.3% | -3.5% | 64.1% |

## 5. Active Warnings
- **[HIGH]** BTC: AVOID (risk-adjusted score -3.51)
- **[MEDIUM]** GLD: REDUCE (risk-adjusted score -0.64)
- **[MEDIUM]** TLT: REDUCE (risk-adjusted score -1.52)

## 6. Indonesia Macro Layer
- Inflation: nan% YoY (contained)
- BI rate proxy: 6.06% (hiking)
- USD/IDR: 17865.0 (weakening over 3m)
- Trade balance: widening surplus
  - ⚠️ bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate
  - ⚠️ usdidr is quarterly data forward-filled to monthly — not a real monthly read
  - ⚠️ This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)

---
*Generated automatically. Every number above traces back to a specific engine — see the corresponding module for methodology and caveats. This is a decision-support tool, not financial advice.*