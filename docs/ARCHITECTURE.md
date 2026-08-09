# GEM Project — Architecture

## Vision

An AI macro investment analyst that:
1. reads global (and eventually Indonesian) economic conditions,
2. classifies the current economic regime,
3. forecasts how that regime is likely to shift over 1/3/6/12 months and 2-4 years,
4. scores tracked assets and issues BUY/HOLD/REDUCE/AVOID calls,
5. projects BTC across multiple horizons,
6. watches for warning conditions automatically, and
7. writes an automated analyst report tying all of the above together.

## Folder layout

```
GEM_PROJECT/
├── config/settings.py          # single source of truth: paths, feature lists, regime taxonomy
├── data/
│   ├── migrate_legacy_export.py    # one-time: old export -> canonical structure
│   └── processed/master_dataset.parquet   # THE dataset — one file, not eight
├── models/
│   ├── scaler.pkl               # one scaler
│   ├── kmeans.pkl               # one clustering model
│   ├── regime_map.json          # one id->name mapping, re-derived + validated at migration time
│   └── transition_matrices/*.csv
├── engines/                     # all computation lives here, nowhere else
│   ├── regime_engine.py          # current regime + probabilities + confidence
│   ├── transition_engine.py      # forward regime probabilities, risk flags
│   ├── risk_engine.py            # regime-conditional asset stats, risk scoring
│   ├── allocation_engine.py      # BUY/HOLD/REDUCE/AVOID
│   ├── btc_forecast_engine.py    # multi-horizon Monte Carlo scenario ranges
│   ├── indonesia_macro_engine.py # NOT YET IMPLEMENTED — scaffold + target schema only
│   └── alert_engine.py           # threshold-based warnings, Telegram-ready template
├── reports/report_generator.py  # narrative markdown synthesis of every engine
├── dashboard/app.py             # Streamlit UI — thin, renders only, no computation
├── tests/test_pipeline_consistency.py  # guards against the bug classes found in the audit
├── archive/                     # every superseded legacy file, kept for reference
└── docs/                        # this file, AUDIT_REPORT.md, CHANGELOG.md
```

## Core design rule: one source of truth, enforced structurally

The legacy project's core bug wasn't really "a bug" — it was an
architecture that made the bug inevitable: two files could each claim
to be the regime map, and nothing stopped code from mixing them. This
version enforces single-source-of-truth by construction:

- Every engine imports paths from `config.settings.PATHS` — never a
  hardcoded string.
- `RegimeEngine` is the ONLY place a raw cluster integer is ever
  produced or consumed. Every other engine (`risk_engine`,
  `allocation_engine`, `alert_engine`, `report_generator`) takes a
  regime **name** (string) as input, never an id. This makes the
  "mixing two id-spaces" bug structurally impossible elsewhere in the
  codebase — there's no id to mix by the time data leaves
  `regime_engine`.
- `tests/test_pipeline_consistency.py` runs a static check
  (`test_regime_detection_uses_only_the_canonical_files`) that fails
  the test suite if any `_v2`/`_rebuilt`/`_final` legacy filename
  pattern is ever reintroduced into `regime_engine.py`.

## How to run

```bash
pip install -r requirements.txt

# one-time, only if migrating from an old export:
python data/migrate_legacy_export.py /path/to/old_export .

# sanity check everything is wired correctly:
python -m pytest tests/ -v

# generate today's analyst report:
python reports/report_generator.py

# run the dashboard:
streamlit run dashboard/app.py

# check for warnings (run this on a schedule, e.g. daily cron):
python engines/alert_engine.py
```

## What's real vs. what's a scaffold

| Component | Status |
|---|---|
| Global regime detection | Real, validated (see AUDIT_REPORT.md) |
| Transition forecasting | Real — reuses the transition matrices that already existed but were unused |
| Asset risk stats | Real, computed from actual historical returns |
| Allocation recommendation | Real, but rule-based (transparent scoring, not ML) — see allocation_engine.py docstring for why |
| BTC multi-horizon forecast | Real Monte Carlo bootstrap over actual history — a scenario range, explicitly not a price prediction |
| Alert engine | Real logic; Telegram send function is a template, untested in this sandbox (no network access to api.telegram.org here) |
| Indonesia macro engine | **Scaffold only** — no Indonesian data exists anywhere in the source export. Needs a real data source connected. |
| Report generator | Real, template-based synthesis of the above |
