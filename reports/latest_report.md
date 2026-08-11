# GEM AI Analyst Report — 2026-08-11

**Data as of:** 2026-07-31

## 1. Current Economic Regime
- **Regime:** Inflation Shock
- **Confidence:** nan/100
- **Full probability distribution:** Inflation Shock nan%, Growth Risk-On nan%, Disinflation Normal nan%, Crisis nan%
- **Historical risk level of this regime:** 50.2/100 (avg volatility 8.04%/mo, 52.1% of months negative across tracked assets, sample confidence: medium)

## 2. Regime Transition Forecast (forward-looking risk)
- **1m:** Inflation Shock 92.7%, Growth Risk-On 5.5%, Crisis 1.8%, Disinflation Normal 0.0%
- **3m:** Inflation Shock 80.3%, Growth Risk-On 14.9%, Crisis 4.6%, Disinflation Normal 0.1%
- **6m:** Inflation Shock 65.9%, Growth Risk-On 26.2%, Crisis 7.3%, Disinflation Normal 0.5%
- **12m:** Inflation Shock 47.9%, Growth Risk-On 41.3%, Crisis 9.4%, Disinflation Normal 1.4%

## 3. Asset Recommendations
*(blend of current-regime history + 3m forward transition-weighted return, risk-adjusted for volatility)*

| Asset | Call | Current-regime mean/mo | Forward blend | Volatility | Score |
|---|---|---|---|---|---|
| BTC | **AVOID** | -1.39% | -0.22% | 19.94% | -3.8 |
| QQQ | **HOLD** | 0.56% | 1.02% | 6.7% | -0.21 |
| SPY | **HOLD** | 0.74% | 0.95% | 5.36% | 0.04 |
| GLD | **HOLD** | -0.09% | 0.43% | 3.88% | -0.41 |
| TLT | **REDUCE** | -0.9% | -0.57% | 4.32% | -1.38 |

## 4. BTC Multi-Horizon Scenario Ranges
*(Monte Carlo bootstrap over historical regime-conditional returns — a scenario range, not a prediction)*

| Horizon | p5 (bad case) | p25 | p50 (median) | p75 | p95 (good case) | P(positive) |
|---|---|---|---|---|---|---|
| 1m | -35.4% | -15.7% | -3.6% | 13.3% | 39.8% | 40.9% |
| 2m | -42.1% | -21.7% | -5.0% | 15.1% | 48.0% | 42.7% |
| 3m | -47.6% | -26.5% | -7.5% | 16.5% | 62.3% | 41.1% |
| 6m | -61.8% | -37.0% | -13.3% | 22.0% | 93.1% | 39.3% |
| 12m | -74.6% | -50.1% | -16.3% | 37.1% | 171.0% | 41.0% |
| 2y | -85.6% | -59.3% | -15.7% | 74.7% | 394.1% | 43.9% |
| 3y | -89.5% | -63.8% | -10.4% | 124.4% | 723.9% | 46.7% |
| 4y | -91.7% | -63.9% | -2.6% | 180.5% | 1166.3% | 49.3% |

## 4b. Other Tracked Assets — 12-Month and 4-Year Scenario Ranges
*(Same Monte Carlo methodology as BTC above, applied per-asset — closes the "multi-horizon forecasting is BTC-only" gap using the same engine, not a new one)*

| Asset | 12m p5 | 12m p50 | 12m p95 | 4y p5 | 4y p50 | 4y p95 |
|---|---|---|---|---|---|---|
| QQQ | -25.6% | 12.0% | 72.0% | -13.8% | 92.8% | 444.9% |
| SPY | -18.9% | 11.1% | 51.4% | -7.2% | 68.7% | 219.9% |
| GLD | -17.9% | 4.7% | 45.5% | -17.1% | 70.6% | 277.6% |
| TLT | -27.0% | -5.7% | 21.2% | -44.1% | -0.4% | 67.7% |

## 5. Active Warnings
- **[HIGH]** BTC: AVOID (risk-adjusted score -3.8)
- **[MEDIUM]** TLT: REDUCE (risk-adjusted score -1.38)

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