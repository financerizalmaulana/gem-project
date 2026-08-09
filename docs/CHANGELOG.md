# Changelog

## v2.5.0 — Two real bugs found via a full GitHub Actions run (2026-08-XX)

First run where the Telegram error-surfacing fix (v2.4.0) actually
paid off — both failures now have clear, actionable causes instead of
opaque "400 Bad Request".

### Fixed
- **FRED 400 error**: the actual error was `api_key=***%0A` — a
  trailing newline in the copy-pasted `FRED_API_KEY` GitHub Secret got
  URL-encoded and FRED rejected it outright. Added defensive
  `.strip()` in two places: `fetch_fred_series` itself (protects any
  direct/Colab usage) and a new `_clean_env` helper in
  `run_pipeline.py` (protects all three env-sourced credentials —
  FRED key, Telegram token, Telegram chat id — at the single point
  they're read from the environment). Added regression tests for both.

### Diagnosed, not a code bug
- **Telegram "chat not found"**: this is a credentials/setup issue,
  not a code defect — either TELEGRAM_CHAT_ID is wrong or the bot was
  never messaged first (Telegram bots can't initiate a conversation).
  Confirmed the v2.4.0 error-surfacing fix works as intended — this
  reason would have been invisible before that fix.

## v2.4.0 — Telegram 400 error made debuggable, HTML-escaping bug fixed (2026-08-XX)

A real GitHub Actions run reached `notification` for the first time
and got `400 Client Error: Bad Request` — but with no way to tell WHY,
because `resp.raise_for_status()` only reports the status code, not
the JSON body Telegram sends back describing the specific reason.

### Fixed
- `send_via_telegram` now captures and surfaces Telegram's actual
  `description` field (e.g. "chat not found", "can't parse entities")
  instead of a bare status code.
- `build_telegram_payload` now HTML-escapes message text. Found while
  fixing the above: `check_regime_change`'s message format
  ("Regime changed: A -> B") contains a literal `>` — with
  `parse_mode=HTML` that WOULD have broken the very first real regime
  change notification, whether or not it's what caused this specific
  400. Closed proactively rather than waiting to hit it.
- Added `test_send_via_telegram_surfaces_real_error_reason` and
  updated existing Telegram tests for the `resp.ok` check (replacing
  `raise_for_status()`) and the new escaping.

### Still open
The actual root cause of the specific 400 seen in the GitHub Actions
run (`400 Client Error: Bad Request for url: .../sendMessage`) is not
yet confirmed — could be an invalid chat_id, a bot token issue, or the
HTML-escaping bug above. Re-running with this fix will surface the
real reason in the logs.

## v2.3.1 — Partial-month bug found via live testing (2026-08-04)

Real Colab run of `fetch_asset_prices.py --dry-run` (its first-ever
live execution) returned `"date": "2026-08-31"` while it was still
August 4th. Root cause: `resample("ME").last()` creates a bucket for
the current, still-in-progress month too, populated with whatever the
latest trading day's close happens to be — not a real month-end price.
This also silently affected `fetch_macro_data.py`'s gold fetch (same
shared function): gold_yoy in that same test run was very likely
computed from a contaminated in-progress-August price, even though the
overall row got correctly labeled June 2026 by unrelated logic (FRED's
own publication lag masked the symptom there).

### Fixed
- `fetch_yfinance_monthly_close` (data/fetch_asset_prices.py) now
  explicitly drops any month that hasn't finished yet, comparing
  calendar periods rather than trusting the resample bucket.
- Added `test_fetch_yfinance_monthly_close_excludes_in_progress_current_month`
  as a permanent regression test for this exact failure mode.

## v2.3.0 — stooq -> yfinance switch (2026-08-04)

The i=m -> i=d fix in v2.2.0 did NOT resolve the gold 404 — retested
live, same error. Investigated properly this time (web search, not
another guess) and found the real cause: stooq began requiring an API
key for anonymous CSV downloads in March 2026. No free-tier fix
exists for that. Switched both gold (in fetch_macro_data.py) and all
5 tracked assets (fetch_asset_prices.py) to yfinance instead.

### Changed
- `data/fetch_asset_prices.py`: stooq -> yfinance (`yf.Ticker(...).history()`).
  Ticker mapping changed: BTC-USD, QQQ, SPY, GLD, TLT (no more
  stooq's ".us"/no-suffix inconsistency).
- `data/fetch_macro_data.py`: `fetch_gold_series` now reuses
  `fetch_yfinance_monthly_close` from fetch_asset_prices.py (ticker
  GC=F) instead of its own stooq call — removes duplicate fetch logic
  between the two modules.
- `requirements.txt`: added `yfinance`.
- Both modules' docstrings rewritten to document the full stooq ->
  paywall -> yfinance history, and to set honest expectations: free
  market data sources break periodically (this is the second time
  gold's source specifically has broken), and yfinance itself is
  independently reported as fragile (unofficial, breaks when Yahoo
  changes their site, though actively patched). This is normal
  maintenance for any system built on free data, not a one-time fix.
- Tests updated to mock `fetch_yfinance_monthly_close` instead of
  `fetch_stooq_monthly_close`, with yfinance-style tickers.

### Still not live-verified
The yfinance switch itself hasn't been run for real yet — that's the
next thing to test in Colab.

## v2.2.0 — First real live execution (2026-08-04)

Ran `python data/fetch_macro_data.py --dry-run` for real, in Colab, for
the first time in this project's history. Result: 9 of 10 FRED series
(cpi, fed_rate, unemployment, oil, dxy, us10y, vix, indpro, neworder)
worked correctly with plausible values on the first try. GPR fetch
also succeeded. `is_new_month: false` was correctly returned — FRED's
June 2026 data is still the latest available as of early August 2026
due to normal publication lag, not a bug.

### Fixed
- Gold fetch (`fetch_gold_series` in `data/fetch_macro_data.py`) 404'd:
  `https://stooq.com/q/d/l/?s=xauusd&i=m` doesn't work — stooq needs
  `i=d` (daily) for this ticker, resampled to monthly afterward (the
  function already did the resample step; only the fetch URL was wrong).
  Confirmed the fix against a working example found via web search.
- Applied the same `i=m` -> `i=d` fix proactively to
  `data/fetch_asset_prices.py` (BTC/QQQ/SPY/GLD/TLT), since it uses
  the identical URL pattern that just failed for gold. Not yet
  confirmed live for these 5 specifically — next thing to test.

## v2.1.0 — Gap-closing pass (2026-07-31)

Baseline for this pass: v2.0.0's Gap Analysis (see chat), used as the
task list per explicit instruction. No architecture changes — every
item below extends the existing engine boundaries.

### Added
- `data/fetch_macro_data.py` — automated FRED-based macro data ingestion, upserts into `master_dataset.parquet`, recomputes regime via the canonical `RegimeEngine`. Closes the #1 gap: the dataset was static with nothing to refresh it.
- `engines/indonesia_macro_engine.py` — upgraded from a pure scaffold to a real (though untested-here) fetch + rule-based directional assessment (inflation/rate/IDR trend), deliberately not a full regime classifier — see module docstring for why.
- `engines/backtest_engine.py` — walk-forward validation of allocation-engine calls, and calibration/coverage test of the BTC forecast's percentile bands. Actually run in this session (no network needed) — see real results in chat.
- `run_pipeline.py` — single orchestrator entry point (data refresh → alerts → report → Telegram) for any scheduler to call.
- `.github/workflows/gem_daily.yml` — the actual scheduler: a GitHub Actions cron job, since this environment can't host a persistent process.
- `engines/alert_engine.py::check_data_freshness` — new check: flags if the dataset hasn't advanced in >45 days, so a silently-broken data pipeline doesn't go unnoticed.
- `engines/btc_forecast_engine.py` — added the missing 2-month horizon (was 1/3/6/12m/2-4y, explicitly requested horizons were 1/2/3/6/12m/2-4y).
- `tests/test_fetch_macro_data.py`, `tests/test_indonesia_macro_engine.py`, `tests/test_run_pipeline.py`, 2 new tests in `tests/test_alert_engine.py` — 27 tests total, all passing.

### Fixed (found via actual web_search verification in this session, not assumed)
- `GOLDPMGBD228NLBM` (the gold FRED series) is confirmed discontinued by FRED itself. Replaced with a stooq.com fallback (`fetch_gold_series`), fails soft to the last known value rather than breaking the whole update.
- Corrected a docstring in `fetch_macro_data.py` that claimed FRED series were "verified via web search" with no evidence that had actually happened — replaced with an honest account of what was and wasn't verified this session.

### Explicitly NOT done (see chat for full reasoning)
- No live end-to-end execution of any external API (FRED, stooq, Telegram, GitHub Actions) — this sandbox's network allowlist blocks all of them (confirmed via direct curl tests, all 403). Must be verified once in a real environment before trusting unattended.
- Asset universe not expanded beyond the original 5 (BTC/QQQ/SPY/GLD/TLT) — no reachable crypto price data source to add ETH/SOL with real numbers.

## v2.0.0 — Full architecture rebuild (2026-07-30)

### Added
- `config/settings.py` — single source of truth for paths, feature lists, regime taxonomy
- `data/migrate_legacy_export.py` — one-time migration tool, doubles as an audit trail
- `models/regime_map.json` — regime mapping re-derived from centroid signature matching (not a static hand-saved dict)
- `engines/regime_engine.py` — regime detection + probability + confidence score
- `engines/transition_engine.py` — forward regime probability forecasting (1/3/6/12m), risk flagging
- `engines/risk_engine.py` — regime-conditional asset statistics + regime risk scoring
- `engines/allocation_engine.py` — BUY/HOLD/REDUCE/AVOID recommendation engine
- `engines/btc_forecast_engine.py` — regime-switching Monte Carlo BTC scenario ranges (1m to 4y)
- `engines/indonesia_macro_engine.py` — scaffold + target schema for the not-yet-built Indonesia layer
- `engines/alert_engine.py` — regime-change detection, low-confidence flags, transition risk flags, asset-call flags; Telegram send template
- `reports/report_generator.py` — automated narrative markdown report synthesizing every engine
- `dashboard/app.py` — rebuilt Streamlit UI (thin, no computation)
- `tests/test_pipeline_consistency.py` — 8 regression tests, all passing
- `docs/ARCHITECTURE.md`, `docs/AUDIT_REPORT.md`, this file
- `requirements.txt`

### Fixed
- Asset Ranking panel indexing by an incompatible cluster-id space (showed wrong regime's asset performance) — see AUDIT_REPORT.md Bug 1
- Determined and documented which of two competing regime maps was actually correct — see AUDIT_REPORT.md Bug 2
- `sort_values()` on a partially-null date column silently reordering the dataset — see AUDIT_REPORT.md Bug 3

### Archived (kept in `archive/`, not deleted)
- 21 legacy files — duplicate models, orphaned PCA-era files, superseded rebuild attempts, empty files. Full list and reasoning in `docs/AUDIT_REPORT.md`.

### Not yet implemented (see docs/ARCHITECTURE.md "what's real vs scaffold")
- Indonesia macro layer (no data source connected yet)
- Live Telegram delivery (logic is written; network send is untested in this environment)
- AI-analyst free-text commentary layer (current report generator is template-based by design, not LLM-generated, to guarantee numeric fidelity)
