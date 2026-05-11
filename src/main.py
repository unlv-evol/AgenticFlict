from __future__ import annotations

import sys
import os
from uuid import uuid4
from collections import defaultdict

import pandas as pd
from tqdm import tqdm

from config import (
    GITHUB_TOKENS,
    OUT_PR,
    OUT_REGIONS,
    OUT_CONFLICT_FILES,
    OUT_CONFLICT_FILE_COMMITS,
    OUT_REPO,
    OUT_RUNLOG,
    MAX_PRS,
)
from github_client import GitHubTokenPool
from hf_loader import load_hf_split
from extractor import prepare_prs, extract_one
from git_ops import ensure_repo


def append_df(df: pd.DataFrame, path: str, dedupe_subset: list[str] | None = None) -> None:
    """Append a DataFrame to a CSV file with optional deduplication.

    Args:
        df: DataFrame to append. No-op if ``None`` or empty.
        path: Destination CSV file path. Created if it does not exist.
        dedupe_subset: Column names used to identify duplicates. When
            provided the entire file is rewritten with duplicates removed
            (last occurrence kept). When ``None``, rows are appended
            directly without deduplication.
    """
    if df is None or df.empty:
        return

    if dedupe_subset is None:
        write_header = not os.path.exists(path)
        df.to_csv(path, mode="a", header=write_header, index=False)
        return

    if os.path.exists(path):
        old = pd.read_csv(path)
        merged = pd.concat([old, df], ignore_index=True)
        merged = merged.drop_duplicates(subset=dedupe_subset, keep="last")
        merged.to_csv(path, index=False)
    else:
        df.drop_duplicates(subset=dedupe_subset, keep="last").to_csv(path, index=False)


def load_done_pr_keys(pr_path: str, retry_failed: bool = False) -> set[str]:
    """Load the set of already-processed PR keys from a prior run.

    Args:
        pr_path: Path to the PR output CSV written by a previous run.
        retry_failed: When ``True``, exclude rows whose ``status_code``
            starts with ``ERR_`` so that previously failed PRs are
            re-attempted in the current run.

    Returns:
        Set of ``pr_key`` strings to skip. Returns an empty set if the
        file does not exist or cannot be read.
    """
    if not os.path.exists(pr_path):
        return set()

    try:
        df = pd.read_csv(pr_path, usecols=["pr_key", "status_code"])
    except Exception:
        return set()

    if "pr_key" not in df.columns:
        return set()

    df["pr_key"] = df["pr_key"].astype(str)

    if not retry_failed and "status_code" in df.columns:
        return set(df["pr_key"].dropna().tolist())

    if retry_failed and "status_code" in df.columns:
        done = df.loc[~df["status_code"].astype(str).str.startswith("ERR_"), "pr_key"]
        return set(done.dropna().tolist())

    return set(df["pr_key"].dropna().tolist())


def group_prs_by_repo(prs: pd.DataFrame) -> dict[str, list[dict]]:
    """Group a DataFrame of PR records by repository.

    Args:
        prs: DataFrame with at least a ``repo_full_name`` column.

    Returns:
        Mapping of ``repo_full_name`` to a list of row dicts for that
        repository. Grouping improves cache locality when processing
        multiple PRs from the same repository.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in prs.to_dict(orient="records"):
        grouped[r["repo_full_name"]].append(r)
    return grouped


def main() -> int:
    """Entry point for the AgenticFlict extraction pipeline.

    Loads PR records from the configured HuggingFace dataset (or local
    Parquet), normalises them, groups by repository, clones/fetches each
    repository once, then runs merge simulation for every PR. Supports
    checkpoint/resume: already-processed PR keys are skipped on restart.
    Set ``RETRY_FAILED=1`` in the environment to re-run errored PRs.

    Returns:
        Exit code: ``0`` on success, ``2`` if no GitHub tokens are configured.
    """
    if not GITHUB_TOKENS:
        print("ERROR: Set GITHUB_TOKENS in .env (comma-separated).")
        return 2

    raw_df = load_hf_split()
    gh = GitHubTokenPool(GITHUB_TOKENS)

    prs = prepare_prs(raw_df)

    # Optional cap for debugging/smaller runs
    if MAX_PRS > 0:
        prs = prs.head(MAX_PRS).copy()

    # Resume support
    retry_failed = os.environ.get("RETRY_FAILED", "0") == "1"
    done_pr_keys = load_done_pr_keys(OUT_PR, retry_failed=retry_failed)

    if done_pr_keys:
        prs = prs[~prs["pr_key"].isin(done_pr_keys)].copy()

    print(f"[RESUME] Already processed PRs: {len(done_pr_keys)}")
    print(f"[RESUME] Remaining PRs to process: {len(prs)}")
    print("[INFO] Storing only OPEN and CLOSED-unmerged PRs.")

    if len(prs) == 0:
        print("[OK] Nothing to do.")
        return 0

    # Sorting improves locality before grouping
    prs = prs.sort_values(["repo_full_name", "pr_number"]).copy()
    grouped = group_prs_by_repo(prs)

    print(f"[INFO] Repositories to process: {len(grouped)}")

    run_id = str(uuid4())

    for repo_full_name, repo_prs in tqdm(grouped.items(), total=len(grouped), desc="Repositories"):
        try:
            repo_path = ensure_repo(repo_full_name)
        except Exception as e:
            # Repo-level failure: emit one fallback row per PR in this repo
            for r in repo_prs:
                pr_key = r["pr_key"]
                pr_number = int(r["pr_number"])

                fallback = pd.DataFrame([{
                    "run_id": run_id,
                    "extracted_at": "",
                    "pipeline_version": "",
                    "pr_key": pr_key,
                    "repo_full_name": repo_full_name,
                    "pr_number": pr_number,
                    "agent": r.get("agent"),
                    "status_code": "ERR_REPO_FETCH",
                    "error_class": "repo",
                    "error_message_trunc": str(e)[:300],
                }])

                fallback_runlog = pd.DataFrame([{
                    "run_id": run_id,
                    "pr_key": pr_key,
                    "repo_full_name": repo_full_name,
                    "pr_number": pr_number,
                    "status_code": "ERR_REPO_FETCH",
                    "error_class": "repo",
                    "error_message_trunc": str(e)[:300],
                }])

                append_df(fallback, OUT_PR)
                append_df(fallback_runlog, OUT_RUNLOG)

            continue

        # Process all PRs for this repository using the same local clone/fetch
        for r in repo_prs:
            try:
                pr_df, regions_df, conflict_files_df, repo_df, runlog_df, conflict_file_commits_df = extract_one(
                    r,
                    gh,
                    run_id,
                    repo_path=repo_path,   # requires extractor.py update
                )
            except Exception as e:
                pr_key = r["pr_key"]
                pr_number = int(r["pr_number"])

                fallback = pd.DataFrame([{
                    "run_id": run_id,
                    "extracted_at": "",
                    "pipeline_version": "",
                    "pr_key": pr_key,
                    "repo_full_name": repo_full_name,
                    "pr_number": pr_number,
                    "agent": r.get("agent"),
                    "status_code": "ERR_UNCAUGHT",
                    "error_class": "unknown",
                    "error_message_trunc": str(e)[:300],
                }])

                fallback_runlog = pd.DataFrame([{
                    "run_id": run_id,
                    "pr_key": pr_key,
                    "repo_full_name": repo_full_name,
                    "pr_number": pr_number,
                    "status_code": "ERR_UNCAUGHT",
                    "error_class": "unknown",
                    "error_message_trunc": str(e)[:300],
                }])

                append_df(fallback, OUT_PR)
                append_df(fallback_runlog, OUT_RUNLOG)
                continue

            append_df(pr_df, OUT_PR)
            append_df(regions_df, OUT_REGIONS)
            append_df(conflict_files_df, OUT_CONFLICT_FILES)
            append_df(conflict_file_commits_df, OUT_CONFLICT_FILE_COMMITS)
            append_df(repo_df, OUT_REPO, dedupe_subset=["repo_full_name"])
            append_df(runlog_df, OUT_RUNLOG)

    print("[OK] Wrote/updated:")
    print(" -", OUT_PR)
    print(" -", OUT_REGIONS)
    print(" -", OUT_CONFLICT_FILES)
    print(" -", OUT_CONFLICT_FILE_COMMITS)
    print(" -", OUT_REPO)
    print(" -", OUT_RUNLOG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())