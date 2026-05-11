"""Loader for the source HuggingFace dataset.

Supports two input modes:

1. **HuggingFace Hub** (default): streams the ``hao-li/AIDev`` dataset
   using the ``datasets`` library.
2. **Local Parquet** (preferred when available): reads a pre-downloaded
   Parquet file specified by :data:`config.HF_PARQUET_PATH`.

Both modes apply an early state filter (:func:`_filter_open_closed`) that
removes merged PRs before any further processing, reducing downstream work.
"""
# from __future__ import annotations

# import os
# from typing import Optional

# import pandas as pd
# from datasets import load_dataset, get_dataset_config_names

# from config import (
#     HF_DATASET_NAME,
#     HF_CONFIG,
#     HF_SPLIT,
#     HF_LIMIT,
#     HF_PARQUET_PATH,
#     HF_PARQUET_ENGINE,
#     HF_TOKEN,
# )


# def pick_config() -> Optional[str]:
#     configs = get_dataset_config_names(HF_DATASET_NAME)
#     if HF_CONFIG and HF_CONFIG in configs:
#         return HF_CONFIG
#     if configs:
#         return configs[0]
#     return None


# def _load_from_parquet(path: str) -> pd.DataFrame:
#     df = pd.read_parquet(path, engine=HF_PARQUET_ENGINE)
#     if HF_LIMIT > 0:
#         df = df.head(HF_LIMIT).copy()
#     print(f"[HF] Loaded parquet: {path} | Rows: {len(df)}")
#     return df


# def _load_from_hf() -> pd.DataFrame:
#     cfg = pick_config()
#     if cfg:
#         ds = load_dataset(HF_DATASET_NAME, cfg, split=HF_SPLIT, token=HF_TOKEN)
#     else:
#         ds = load_dataset(HF_DATASET_NAME, split=HF_SPLIT, token=HF_TOKEN)

#     if HF_LIMIT > 0:
#         ds = ds.select(range(min(HF_LIMIT, len(ds))))

#     print(f"[HF] Loaded HF: {HF_DATASET_NAME} | Config: {cfg} | Split: {HF_SPLIT} | Rows: {len(ds)}")
#     return ds.to_pandas()


# def load_hf_split() -> pd.DataFrame:
#     # Prefer local parquet if provided and exists
#     if HF_PARQUET_PATH and os.path.exists(HF_PARQUET_PATH):
#         return _load_from_parquet(HF_PARQUET_PATH)

#     return _load_from_hf()


from __future__ import annotations

import os
from typing import Optional

import pandas as pd
from datasets import load_dataset, get_dataset_config_names

from config import (
    HF_DATASET_NAME,
    HF_CONFIG,
    HF_SPLIT,
    HF_LIMIT,
    HF_PARQUET_PATH,
    HF_PARQUET_ENGINE,
)


def pick_config() -> Optional[str]:
    """Select the HuggingFace dataset configuration to use.

    Honours :data:`config.HF_CONFIG` if it names a valid configuration.
    Falls back to the first available configuration otherwise.

    Returns:
        Configuration name string, or ``None`` if no configurations are
        defined for the dataset.
    """
    configs = get_dataset_config_names(HF_DATASET_NAME)
    if HF_CONFIG and HF_CONFIG in configs:
        return HF_CONFIG
    if configs:
        return configs[0]
    return None


# def _filter_open_closed(df: pd.DataFrame) -> pd.DataFrame:
#     """
#     Keep only rows whose raw PR state is OPEN or CLOSED if a state column exists.
#     If no state column exists, return the dataframe unchanged and let downstream
#     GraphQL filtering decide.
#     """
#     state_cols = ["state", "pr_state", "pull_request_state"]
#     state_col = next((c for c in state_cols if c in df.columns), None)

#     if state_col is None:
#         print("[HF] No raw state column found; skipping early state filter.")
#         return df

#     s = df[state_col].astype(str).str.upper().str.strip()
#     out = df[s.isin(["OPEN", "CLOSED"])].copy()
#     print(f"[HF] Early state filter on '{state_col}': kept {len(out)}/{len(df)} rows")
#     return out

def _filter_open_closed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only:
        - OPEN PRs
        - CLOSED PRs where merged_at is NULL

    If the dataset does not contain state or merged_at information,
    the dataframe is returned unchanged and filtering will occur later
    using GitHub GraphQL metadata.
    """

    # Possible state column names
    state_cols = ["state", "pr_state", "pull_request_state"]
    state_col = next((c for c in state_cols if c in df.columns), None)

    # Possible merge timestamp columns
    merged_cols = ["merged_at", "mergedAt", "merge_time"]
    merged_col = next((c for c in merged_cols if c in df.columns), None)

    if state_col is None:
        print("[HF] No raw state column found; skipping early state filter.")
        return df

    s = df[state_col].astype(str).str.upper().str.strip()

    open_mask = s == "OPEN"

    if merged_col is not None:
        closed_unmerged_mask = (s == "CLOSED") & (df[merged_col].isna())
    else:
        # If merged info missing, keep CLOSED and let GraphQL decide later
        closed_unmerged_mask = s == "CLOSED"

    out = df[open_mask | closed_unmerged_mask].copy()

    print(
        f"[HF] Early state filter on '{state_col}' "
        f"(merged column: {merged_col}): kept {len(out)}/{len(df)} rows"
    )

    return out


def _load_from_parquet(path: str) -> pd.DataFrame:
    """Load PR records from a local Parquet file.

    Args:
        path: Filesystem path to the Parquet file.

    Returns:
        Filtered DataFrame (OPEN and CLOSED-unmerged PRs only), optionally
        capped at :data:`config.HF_LIMIT` rows.
    """
    df = pd.read_parquet(path, engine=HF_PARQUET_ENGINE)
    df = _filter_open_closed(df)

    if HF_LIMIT > 0:
        df = df.head(HF_LIMIT).copy()

    print(f"[HF] Loaded parquet: {path} | Rows: {len(df)}")
    return df


def _load_from_hf() -> pd.DataFrame:
    """Load PR records from the HuggingFace Hub.

    Uses :func:`pick_config` to select the dataset configuration and loads
    :data:`config.HF_SPLIT`. Large datasets are capped at
    :data:`config.HF_LIMIT` rows before the state filter is applied.

    Returns:
        Filtered DataFrame (OPEN and CLOSED-unmerged PRs only).
    """
    cfg = pick_config()
    if cfg:
        ds = load_dataset(HF_DATASET_NAME, cfg, split=HF_SPLIT)
    else:
        ds = load_dataset(HF_DATASET_NAME, split=HF_SPLIT)

    if HF_LIMIT > 0:
        ds = ds.select(range(min(HF_LIMIT, len(ds))))

    df = ds.to_pandas()
    df = _filter_open_closed(df)

    print(f"[HF] Loaded HF: {HF_DATASET_NAME} | Config: {cfg} | Split: {HF_SPLIT} | Rows: {len(df)}")
    return df


def load_hf_split() -> pd.DataFrame:
    """Load the source PR dataset using the configured input mode.

    Prefers a local Parquet file (:data:`config.HF_PARQUET_PATH`) when
    available; falls back to the HuggingFace Hub otherwise.

    Returns:
        DataFrame of OPEN and CLOSED-unmerged PR records ready for
        :func:`extractor.prepare_prs`.
    """
    if HF_PARQUET_PATH and os.path.exists(HF_PARQUET_PATH):
        return _load_from_parquet(HF_PARQUET_PATH)
    return _load_from_hf()



