# GEM Project — Audit Report

Audit performed on the Google Drive export `drive-download-20260729T034250Z-1-001.zip`
(24 files). Every claim below was verified by actually loading the
files and running the code, not by inspection alone.

## Bug 1 (critical, active): Asset Ranking showed the wrong regime's data

`dashboard.py` computed the current regime using `kmeans_regime.pkl` +
`regime_map_final.pkl` (giving `pred_cluster = 1` → "Growth Risk-On"
for 2026-06-30), then used that same raw integer `1` to index into
`regime_asset_rebuilt.parquet`'s `cluster_rebuilt` column — a
**different id-space** where `1 = "Crisis"`. The dashboard displayed
"Current Regime: Growth Risk-On" while the Asset Ranking table below
it silently showed Crisis-regime asset returns. No error was thrown —
this is the dangerous kind of bug.

**Root cause:** two independent id→label mappings coexisted
(`regime_map_final.pkl` vs `regime_map_rebuilt.pkl`), and the code
mixed them.

**Fix:** `RegimeEngine` is now the only place a raw cluster id is ever
produced; every other engine consumes a regime **name** (string).
Structurally impossible to mix id-spaces because there's no id left
to mix downstream. See `tests/test_allocation_engine_never_indexes_by_raw_cluster_int`.

## Bug 2 (critical, resolved): which regime map is actually correct

Three lineages disagreed on the regime for 2026-06-30:
`cluster_name` (original) = "Growth Risk-On"; `cluster_name_rebuilt`
and `cluster_name_new` (two separate "fix" attempts) = "Inflation
Shock".

**Resolution method:** inverse-transformed `kmeans_regime.pkl`'s
cluster centers back to raw units and compared them against the
project's own earlier validated centroid signature (the AUDIT 4 output
from an earlier session, cross-checked again against AUDIT 5's sample
counts). The match was almost exact (distance ≈0.01 across all 4
clusters × 7 signature features), which exactly reproduces
`regime_map_final.pkl`. `regime_map_rebuilt.pkl` does **not** match
this signature — it appears to have introduced a labeling error during
a later, well-intentioned but incorrect rebuild attempt.

**Conclusion:** `regime_map_final.pkl` / the original `cluster_name`
lineage is correct. The dashboard's live output ("Growth Risk-On") was
right all along — only the Asset Ranking join (Bug 1) was wrong. The
"_rebuilt"/"_new" lineage is archived with a note explaining why, not
used as source of truth, but kept in case this judgment ever needs
revisiting.

**Caveat:** this conclusion is as rigorous as the available evidence
allows, but it rests on one independent reference point (the AUDIT 4
signature). If you have any other record of which pipeline was
considered correct at the time, it's worth a second look before
trusting this for real allocation decisions.

## Bug 3 (data quality, found during migration): sort_values() silently reordered the dataset

`regime_asset_rebuilt.parquet`'s `date` column had `NaT` for its
earliest 12 rows (a leftover artifact from an old merge/rolling-window
step) — `date_x` was fully populated for the same rows. `pandas.sort_values()`
pushes `NaT` to the end by default, so a naive `sort_values("date")`
during migration silently moved the 12 OLDEST rows (2010) to the very
end, making them look like the newest data. Caught by
`test_master_dataset_latest_row_is_actually_latest` before it could
propagate into any engine. Fixed by using `date_x` (fully populated)
as the canonical date column.

## Duplicated / orphaned files found

| File | Finding |
|---|---|
| `kmeans.pkl` | byte-identical to `kmeans_regime.pkl` |
| `scaler.pkl`, `models/scaler.pkl` | both identical to `scaler_regime.pkl` (3 copies of the same object) |
| `models/kmeans.pkl` | different — fit on 4 dimensions, belongs to an abandoned PCA-based approach, unused by any live code |
| `models/pca.pkl` | PCA(0.7 variance), unused — live pipeline uses 11 raw scaled features directly |
| `regime_transition_matrix_v2.csv` | byte-identical content to `models/transition_matrix_1m.csv` |
| `master_regime_v2.csv` vs `master_regime_rebuilt.csv` | two separate rebuild attempts; agree on the last ~12 months but disagree on 130/186 historical rows |
| `data/master_final.csv`, `data/regime_asset.csv` | early-stage staging files, superseded by the parquet versions |
| `gem_live_v2.py` | 0 bytes — empty file |
| `docs/`, `outputs/` (folders in the zip) | both completely empty |

All of the above were **archived**, not deleted (see `archive/`), each
with a filename suffix explaining why it was set aside.

## Feature audit against the 7 original goals

| Goal | Legacy status | Status after this rebuild |
|---|---|---|
| 1. Local (Indonesia) economic conditions | Not started | Scaffold only (`indonesia_macro_engine.py`) — still needs a real data source |
| 2. Global economic conditions | Built, but with Bug 1 active | Built and fixed |
| 3. Asset analyst + BUY recommendation | Raw data existed, no recommendation logic | Built (`allocation_engine.py`) |
| 4. Forward risk/opportunity (6m/1y) | Transition matrices computed but never used anywhere | Built and wired into dashboard + report (`transition_engine.py`) |
| 5. BTC multi-horizon projection (1-12mo, 2-4y) | Not started | Built (`btc_forecast_engine.py`), Monte Carlo scenario ranges with honest wide tails |
| 6. Asset warning system | Not started (`gem_live_v2.py` empty) | Built (`alert_engine.py`) — logic is real, Telegram send is an untested template |
| 7. Economic/regime change warnings | Not started | Built — regime-change detection + forward transition risk flags in `alert_engine.py` |
