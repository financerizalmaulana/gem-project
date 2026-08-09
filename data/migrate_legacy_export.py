"""
ONE-TIME MIGRATION SCRIPT
=========================
Converts the old, duplicated GEM_PROJECT Drive export into the new
canonical structure. Run this ONCE against your old Drive folder.
After this runs successfully, the new engines/dashboard never touch
the legacy files again — they only read from config.PATHS.

Usage:
    python migrate_legacy_export.py /path/to/old_export /path/to/GEM_PROJECT

What this does and WHY (audit trail):
--------------------------------------
1. Regime mapping conflict (regime_map_final.pkl vs regime_map_rebuilt.pkl):
   RESOLVED in favor of `regime_map_final.pkl` / `kmeans_regime.pkl` /
   the original `cluster` + `cluster_name` columns.
   Proof: inverse-transforming kmeans_regime.pkl's cluster centers back
   to raw units reproduces the project's own earlier validated AUDIT 4
   centroid table almost exactly (max deviation ~0.01 across all 7
   signature features, for all 4 clusters). The "_rebuilt"/"_new"
   lineage (regime_map_rebuilt.pkl, cluster_rebuilt, cluster_new)
   does NOT match that signature and was introduced by a later,
   incorrect rebuild attempt. It is archived, not deleted, in case
   this judgment ever needs to be revisited.

2. Duplicate models (kmeans.pkl == kmeans_regime.pkl,
   scaler.pkl == scaler_regime.pkl == models/scaler.pkl):
   Kept exactly one copy of each in models/. Archived the rest.

3. Orphaned PCA-era files (models/pca.pkl, models/kmeans.pkl [4-dim]):
   The live pipeline uses 11 raw scaled features directly, no PCA step.
   These belong to an earlier, abandoned PCA-based approach. Archived.

4. Duplicate transition matrix (regime_transition_matrix_v2.csv is
   byte-identical in content to models/transition_matrix_1m.csv):
   Kept the models/transition_matrix_*m.csv set (has all 4 horizons).
   Archived the duplicate.

5. Master dataset consolidation: previously scattered across
   macro_regime_final.{csv,parquet}, master_clean.parquet,
   master_regime_v2.csv, master_regime_rebuilt.csv,
   regime_asset_rebuilt.parquet, data/master_final.csv,
   data/regime_asset.csv (8 overlapping files!). Consolidated into
   ONE file: data/processed/master_dataset.parquet, built from
   regime_asset_rebuilt.parquet (it has the union of macro features +
   asset returns), keeping only the validated `cluster`/`cluster_name`
   columns and asset returns, dropping the unreliable `_rebuilt`
   columns and merge-artifact duplicate date columns (date_x/date_y).
"""

import sys
import os
import json
import shutil
import joblib
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import MACRO_FEATURES, REGIME_SIGNATURES, SIGNATURE_FEATURES, TRANSITION_HORIZONS


def resolve_regime_map(scaler, kmeans) -> dict:
    """
    Derives the cluster_id -> regime_name mapping FROM THE MODEL ITSELF,
    by comparing inverse-transformed centroids against the known
    validated regime signatures — instead of trusting a static saved
    dict that can silently go stale if the model is ever refit.
    """
    centers_raw = scaler.inverse_transform(kmeans.cluster_centers_)
    centers_df = pd.DataFrame(centers_raw, columns=MACRO_FEATURES)

    ref_names = list(REGIME_SIGNATURES.keys())
    ref_vals = np.array([[REGIME_SIGNATURES[name][f] for f in SIGNATURE_FEATURES] for name in ref_names])
    stds = ref_vals.std(axis=0)
    stds[stds == 0] = 1.0

    center_vals = centers_df[SIGNATURE_FEATURES].values
    dist = cdist(center_vals / stds, ref_vals / stds, metric="euclidean")

    regime_map = {}
    for cluster_id in range(len(centers_df)):
        best_idx = int(np.argmin(dist[cluster_id]))
        best_dist = dist[cluster_id][best_idx]
        regime_map[cluster_id] = ref_names[best_idx]
        if best_dist > 1.0:
            print(f"  WARNING: cluster {cluster_id} best match '{ref_names[best_idx]}' "
                  f"has distance {best_dist:.2f} (>1.0) — signature match is weak, verify manually.")
    return regime_map


def main(legacy_dir: str, project_dir: str):
    models_dir = os.path.join(project_dir, "models")
    transitions_dir = os.path.join(models_dir, "transition_matrices")
    processed_dir = os.path.join(project_dir, "data", "processed")
    archive_models = os.path.join(project_dir, "archive", "models_legacy")
    archive_data = os.path.join(project_dir, "archive", "data_legacy")
    for d in [models_dir, transitions_dir, processed_dir, archive_models, archive_data]:
        os.makedirs(d, exist_ok=True)

    # --- 1. Canonical scaler + kmeans -------------------------------------------------
    scaler = joblib.load(os.path.join(legacy_dir, "scaler_regime.pkl"))
    kmeans = joblib.load(os.path.join(legacy_dir, "kmeans_regime.pkl"))
    joblib.dump(scaler, os.path.join(models_dir, "scaler.pkl"))
    joblib.dump(kmeans, os.path.join(models_dir, "kmeans.pkl"))
    print("[OK] Canonical scaler.pkl and kmeans.pkl written.")

    # --- 2. Canonical regime map (re-derived + validated, saved as JSON not pickle) ---
    regime_map = resolve_regime_map(scaler, kmeans)
    with open(os.path.join(models_dir, "regime_map.json"), "w") as f:
        json.dump({str(k): v for k, v in regime_map.items()}, f, indent=2)
    print(f"[OK] Canonical regime_map.json written: {regime_map}")

    # cross-check against the legacy static dict for transparency in the audit log
    legacy_final = joblib.load(os.path.join(legacy_dir, "regime_map_final.pkl"))
    legacy_rebuilt = joblib.load(os.path.join(legacy_dir, "regime_map_rebuilt.pkl"))
    print(f"    (legacy regime_map_final.pkl   = {legacy_final}  -> {'MATCHES' if legacy_final == regime_map else 'DIFFERS'})")
    print(f"    (legacy regime_map_rebuilt.pkl = {legacy_rebuilt}  -> {'MATCHES' if legacy_rebuilt == regime_map else 'DIFFERS'})")

    # --- 3. Transition matrices (already correct, just relocate) -----------------------
    for h in TRANSITION_HORIZONS:
        src = os.path.join(legacy_dir, "models", f"transition_matrix_{h}.csv")
        dst = os.path.join(transitions_dir, f"transition_matrix_{h}.csv")
        if os.path.exists(src):
            shutil.copy2(src, dst)
    print(f"[OK] Transition matrices copied for horizons: {TRANSITION_HORIZONS}")

    # --- 4. Consolidated master dataset --------------------------------------------
    src = pd.read_parquet(os.path.join(legacy_dir, "regime_asset_rebuilt.parquet"))
    # NOTE: the legacy "date" column (as opposed to "date_x") has NaT for the
    # earliest 12 rows (a leftover artifact from an old merge/rolling-window
    # step). pandas sort_values() pushes NaT rows to the END by default, which
    # silently made the OLDEST rows look like the newest ones after sorting —
    # a second, separate data bug discovered during migration. "date_x" is
    # fully populated and is used as the canonical date field instead.
    keep_cols = ["date_x"] + MACRO_FEATURES + ["cluster", "cluster_name"] + \
                ["btc_ret", "qqq_ret", "spy_ret", "gld_ret", "tlt_ret"]
    master = src[keep_cols].copy().rename(columns={"date_x": "date"})
    master["date"] = pd.to_datetime(master["date"])
    master = master.sort_values("date").reset_index(drop=True)
    assert master["date"].isna().sum() == 0, "date column still has NaT after migration fix — investigate"
    master = master.rename(columns={"cluster": "cluster_id", "cluster_name": "regime"})
    master.to_parquet(os.path.join(processed_dir, "master_dataset.parquet"), index=False)
    print(f"[OK] master_dataset.parquet written: {master.shape[0]} rows, {master.shape[1]} cols, "
          f"{master['date'].min().date()} to {master['date'].max().date()}")

    # --- 5. Archive everything superseded (kept, not deleted) --------------------------
    archive_map = {
        os.path.join(legacy_dir, "kmeans.pkl"): os.path.join(archive_models, "kmeans_DUPLICATE_of_kmeans_regime.pkl"),
        os.path.join(legacy_dir, "scaler.pkl"): os.path.join(archive_models, "scaler_DUPLICATE.pkl"),
        os.path.join(legacy_dir, "models", "scaler.pkl"): os.path.join(archive_models, "scaler_DUPLICATE_2.pkl"),
        os.path.join(legacy_dir, "models", "kmeans.pkl"): os.path.join(archive_models, "kmeans_ORPHANED_pca_era_4dim.pkl"),
        os.path.join(legacy_dir, "models", "pca.pkl"): os.path.join(archive_models, "pca_ORPHANED_unused.pkl"),
        os.path.join(legacy_dir, "regime_map_rebuilt.pkl"): os.path.join(archive_models, "regime_map_rebuilt_INCORRECT_mapping.pkl"),
        os.path.join(legacy_dir, "regime_map_final.pkl"): os.path.join(archive_models, "regime_map_final_ORIGINAL_reference.pkl"),
        os.path.join(legacy_dir, "scaler_regime.pkl"): os.path.join(archive_models, "scaler_regime_ORIGINAL_reference.pkl"),
        os.path.join(legacy_dir, "kmeans_regime.pkl"): os.path.join(archive_models, "kmeans_regime_ORIGINAL_reference.pkl"),

        os.path.join(legacy_dir, "master_regime_v2.csv"): os.path.join(archive_data, "master_regime_v2_INCORRECT_rebuild.csv"),
        os.path.join(legacy_dir, "master_regime_rebuilt.csv"): os.path.join(archive_data, "master_regime_rebuilt_INCORRECT_rebuild.csv"),
        os.path.join(legacy_dir, "master_clean.parquet"): os.path.join(archive_data, "master_clean_INCORRECT_rebuild.parquet"),
        os.path.join(legacy_dir, "regime_asset_rebuilt.parquet"): os.path.join(archive_data, "regime_asset_rebuilt_SOURCE_used_for_migration.parquet"),
        os.path.join(legacy_dir, "macro_regime_final.csv"): os.path.join(archive_data, "macro_regime_final_csv_DUPLICATE_of_parquet.csv"),
        os.path.join(legacy_dir, "macro_regime_final.parquet"): os.path.join(archive_data, "macro_regime_final_ORIGINAL_reference.parquet"),
        os.path.join(legacy_dir, "regime_transition_matrix_v2.csv"): os.path.join(archive_data, "regime_transition_matrix_v2_DUPLICATE_of_1m.csv"),
        os.path.join(legacy_dir, "data", "master_final.csv"): os.path.join(archive_data, "data_master_final_STAGING_superseded.csv"),
        os.path.join(legacy_dir, "data", "regime_asset.csv"): os.path.join(archive_data, "data_regime_asset_STAGING_superseded.csv"),
        os.path.join(legacy_dir, "CHECKPOINT_2026_06_08.txt"): os.path.join(archive_data, "CHECKPOINT_2026_06_08.txt"),
        os.path.join(legacy_dir, "dashboard.py"): os.path.join(archive_data, "dashboard_OLD_had_asset_ranking_bug.py"),
        os.path.join(legacy_dir, "gem_live_v2.py"): os.path.join(archive_data, "gem_live_v2_EMPTY_file.py"),
    }
    archived, missing = [], []
    for src_path, dst_path in archive_map.items():
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            archived.append(os.path.basename(src_path))
        else:
            missing.append(os.path.basename(src_path))
    print(f"[OK] Archived {len(archived)} legacy files into archive/.")
    if missing:
        print(f"    (not found, skipped: {missing})")

    print("\nMigration complete.")


if __name__ == "__main__":
    legacy = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/legacy_export"
    project = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(legacy, project)
