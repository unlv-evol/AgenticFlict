from __future__ import annotations

from typing import List, Dict, Any, Tuple
from uuid import uuid4

import pandas as pd
from tqdm import tqdm

from config import MAX_PRS, EXTRACTED_AT, PIPELINE_VERSION
from github_client import GitHubTokenPool
from git_ops import (
    ensure_repo,
    merge_test,
    last_touch_commit,
    conflict_type_for_path,
    resolve_base_oid_before,
)
from normalize import normalize_prs
from schema import PRRow, to_dict


def _err_class(status_code: str) -> str:
    if status_code.startswith("ERR_GH"):
        return "api"
    if status_code.startswith("ERR_REPO"):
        return "repo"
    if status_code.startswith("ERR_MISSING"):
        return "missing_ref"
    if status_code.startswith("ERR_MERGE"):
        return "merge"
    if status_code.startswith("SKIP_"):
        return "filtered"
    return "unknown"


def prepare_prs(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize raw rows into canonical PR rows and add pr_key.
    """
    prs = normalize_prs(raw_df).dropna(subset=["repo_full_name", "pr_number"]).copy()
    prs["pr_number"] = prs["pr_number"].astype(int)
    prs["pr_key"] = prs["repo_full_name"].astype(str) + "#" + prs["pr_number"].astype(str)
    return prs


def extract_one(
    r: Dict[str, Any],
    gh: GitHubTokenPool,
    run_id: str,
    repo_path: str | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Process exactly one PR and return six DataFrames in this order:
      pr_df,
      regions_df,
      conflict_files_df,
      repo_df,
      runlog_df,
      conflict_file_commits_df

    This design supports checkpoint/resume because callers can append
    outputs immediately after each PR.
    """
    repo_full_name = r["repo_full_name"]
    pr_number = int(r["pr_number"])
    agent = r.get("agent")
    pr_key = r.get("pr_key") or f"{repo_full_name}#{pr_number}"

    pr_rows: List[Dict[str, Any]] = []
    region_rows: List[Dict[str, Any]] = []
    conflict_file_rows: List[Dict[str, Any]] = []
    conflict_file_commit_rows: List[Dict[str, Any]] = []
    repo_rows_by_repo: Dict[str, Dict[str, Any]] = {}
    runlog_rows: List[Dict[str, Any]] = []

    pr_row = PRRow(
        run_id=run_id,
        extracted_at=EXTRACTED_AT,
        pipeline_version=PIPELINE_VERSION,
        pr_key=pr_key,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        agent=agent,
    )

    # ------------------------------------------------------------------
    # Step 1: GitHub GraphQL repo + PR metadata
    # ------------------------------------------------------------------
    try:
        owner, name = repo_full_name.split("/", 1)
        data = gh.fetch_repo_and_pr(owner, name, pr_number)
        repo = data["data"]["repository"]
        pr = (repo or {}).get("pullRequest")

        if pr is None:
            pr_row.status_code = "ERR_PR_NOT_FOUND"
            pr_row.error_class = _err_class(pr_row.status_code)

            pr_rows.append(to_dict(pr_row))
            runlog_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "status_code": pr_row.status_code,
                "error_class": pr_row.error_class,
            })
            return (
                pd.DataFrame(pr_rows),
                pd.DataFrame(region_rows),
                pd.DataFrame(conflict_file_rows),
                pd.DataFrame(list(repo_rows_by_repo.values())),
                pd.DataFrame(runlog_rows),
                pd.DataFrame(conflict_file_commit_rows),
            )

        # Only keep repo rows for PRs that are actually stored in the dataset.
        # We do not populate repo_rows_by_repo yet for merged PRs because they
        # are filtered out later and should not appear in repo.csv.

        pr_row.gh_state = pr.get("state")
        pr_row.gh_mergeable_at_extraction = pr.get("mergeable")
        pr_row.created_at = pr.get("createdAt")
        pr_row.closed_at = pr.get("closedAt")
        pr_row.merged_at = pr.get("mergedAt")

        pr_row.pr_additions = pr.get("additions")
        pr_row.pr_deletions = pr.get("deletions")
        pr_row.pr_changed_files = pr.get("changedFiles")
        pr_row.pr_commits = (pr.get("commits") or {}).get("totalCount")

        pr_row.base_ref_name = pr.get("baseRefName")
        pr_row.head_ref_name = pr.get("headRefName")
        pr_row.base_oid = pr.get("baseRefOid")
        pr_row.head_oid = pr.get("headRefOid")
        pr_row.merge_commit_oid = (pr.get("mergeCommit") or {}).get("oid")

        repo_row = {
            "run_id": run_id,
            "extracted_at": EXTRACTED_AT,
            "pipeline_version": PIPELINE_VERSION,
            "repo_full_name": repo.get("nameWithOwner") or repo_full_name,
            "default_branch": (repo.get("defaultBranchRef") or {}).get("name"),
            "primary_language": (repo.get("primaryLanguage") or {}).get("name"),
            "stargazer_count": repo.get("stargazerCount"),
            "fork_count": repo.get("forkCount"),
            "is_archived": repo.get("isArchived"),
            "is_fork": repo.get("isFork"),
        }

    except Exception as e:
        pr_row.status_code = "ERR_GH_API"
        pr_row.error_message_trunc = str(e)[:300]
        pr_row.error_class = _err_class(pr_row.status_code)

        pr_rows.append(to_dict(pr_row))
        runlog_rows.append({
            "run_id": run_id,
            "extracted_at": EXTRACTED_AT,
            "pipeline_version": PIPELINE_VERSION,
            "pr_key": pr_key,
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "status_code": pr_row.status_code,
            "error_class": pr_row.error_class,
            "error_message_trunc": pr_row.error_message_trunc,
        })
        return (
            pd.DataFrame(pr_rows),
            pd.DataFrame(region_rows),
            pd.DataFrame(conflict_file_rows),
            pd.DataFrame(list(repo_rows_by_repo.values())),
            pd.DataFrame(runlog_rows),
            pd.DataFrame(conflict_file_commit_rows),
        )

    # ------------------------------------------------------------------
    # Step 2: Store only OPEN and CLOSED-unmerged PRs
    # Merged PRs are excluded from dataset tables, but logged in runlog.
    # ------------------------------------------------------------------
    if pr_row.gh_state == "CLOSED" and pr_row.merged_at:
        runlog_rows.append({
            "run_id": run_id,
            "extracted_at": EXTRACTED_AT,
            "pipeline_version": PIPELINE_VERSION,
            "pr_key": pr_key,
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "status_code": "SKIP_MERGED_PR",
            "error_class": "filtered",
        })
        return (
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(runlog_rows),
            pd.DataFrame(),
        )

    # Since this PR will be retained, keep the repo row too.
    repo_rows_by_repo[repo_full_name] = repo_row

    # ------------------------------------------------------------------
    # Step 3: Materialize repository locally
    # ------------------------------------------------------------------
    try:
        if repo_path is None:
            repo_path = ensure_repo(repo_full_name)
        # repo_path = ensure_repo(repo_full_name)
    except Exception as e:
        pr_row.status_code = "ERR_REPO_FETCH"
        pr_row.error_message_trunc = str(e)[:300]
        pr_row.error_class = _err_class(pr_row.status_code)

        pr_rows.append(to_dict(pr_row))
        runlog_rows.append({
            "run_id": run_id,
            "extracted_at": EXTRACTED_AT,
            "pipeline_version": PIPELINE_VERSION,
            "pr_key": pr_key,
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "status_code": pr_row.status_code,
            "error_class": pr_row.error_class,
            "error_message_trunc": pr_row.error_message_trunc,
        })
        return (
            pd.DataFrame(pr_rows),
            pd.DataFrame(region_rows),
            pd.DataFrame(conflict_file_rows),
            pd.DataFrame(list(repo_rows_by_repo.values())),
            pd.DataFrame(runlog_rows),
            pd.DataFrame(conflict_file_commit_rows),
        )

    # ------------------------------------------------------------------
    # Step 4: Determine simulation anchors
    # OPEN PRs  -> current base_oid/current head_oid
    # CLOSED PRs -> base branch state at closedAt + available current head_oid
    # ------------------------------------------------------------------
    if not pr_row.head_oid:
        pr_row.status_code = "ERR_MISSING_OID"
        pr_row.error_class = _err_class(pr_row.status_code)
        pr_row.error_message_trunc = "head_oid missing"

        pr_rows.append(to_dict(pr_row))
        runlog_rows.append({
            "run_id": run_id,
            "extracted_at": EXTRACTED_AT,
            "pipeline_version": PIPELINE_VERSION,
            "pr_key": pr_key,
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "status_code": pr_row.status_code,
            "error_class": pr_row.error_class,
            "error_message_trunc": pr_row.error_message_trunc,
        })
        return (
            pd.DataFrame(pr_rows),
            pd.DataFrame(region_rows),
            pd.DataFrame(conflict_file_rows),
            pd.DataFrame(list(repo_rows_by_repo.values())),
            pd.DataFrame(runlog_rows),
            pd.DataFrame(conflict_file_commit_rows),
        )

    if pr_row.gh_state == "OPEN":
        if not pr_row.base_oid:
            pr_row.status_code = "ERR_MISSING_OID"
            pr_row.error_class = _err_class(pr_row.status_code)
            pr_row.error_message_trunc = "base_oid missing for open PR"

            pr_rows.append(to_dict(pr_row))
            runlog_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "status_code": pr_row.status_code,
                "error_class": pr_row.error_class,
                "error_message_trunc": pr_row.error_message_trunc,
            })
            return (
                pd.DataFrame(pr_rows),
                pd.DataFrame(region_rows),
                pd.DataFrame(conflict_file_rows),
                pd.DataFrame(list(repo_rows_by_repo.values())),
                pd.DataFrame(runlog_rows),
                pd.DataFrame(conflict_file_commit_rows),
            )

        pr_row.simulation_mode = "open_current"
        pr_row.simulation_anchor_time = EXTRACTED_AT
        pr_row.base_sim_oid = pr_row.base_oid
        pr_row.head_sim_oid = pr_row.head_oid

    else:
        # closed-unmerged PR
        pr_row.simulation_mode = "closed_base_at_close"
        pr_row.simulation_anchor_time = pr_row.closed_at
        pr_row.head_sim_oid = pr_row.head_oid
        pr_row.base_sim_oid = resolve_base_oid_before(
            repo_path,
            pr_row.base_ref_name,
            pr_row.closed_at,
        )

        if not pr_row.base_sim_oid:
            pr_row.status_code = "ERR_BASE_SIM_OID"
            pr_row.error_class = "missing_ref"
            pr_row.error_message_trunc = "failed to resolve base commit before closedAt"

            pr_rows.append(to_dict(pr_row))
            runlog_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "status_code": pr_row.status_code,
                "error_class": pr_row.error_class,
                "error_message_trunc": pr_row.error_message_trunc,
                "simulation_mode": pr_row.simulation_mode,
                "simulation_anchor_time": pr_row.simulation_anchor_time,
            })
            return (
                pd.DataFrame(pr_rows),
                pd.DataFrame(region_rows),
                pd.DataFrame(conflict_file_rows),
                pd.DataFrame(list(repo_rows_by_repo.values())),
                pd.DataFrame(runlog_rows),
                pd.DataFrame(conflict_file_commit_rows),
            )

    # ------------------------------------------------------------------
    # Step 5: Merge simulation
    # ------------------------------------------------------------------
    ok, metrics, regions, conflict_files, detail = merge_test(
        repo_path,
        pr_row.base_sim_oid,
        pr_row.head_sim_oid,
    )

    if ok:
        pr_row.status_code = "OK_MERGE_CLEAN"
        pr_row.conflict_label = False
    else:
        if metrics and metrics.has_text_conflict:
            pr_row.status_code = "OK_CONFLICT"
            pr_row.conflict_label = True
        else:
            pr_row.status_code = "ERR_MERGE_FAILED"
            pr_row.conflict_label = None

    pr_row.error_class = _err_class(pr_row.status_code)
    pr_row.error_message_trunc = (detail or "")[:300]

    if metrics is not None:
        pr_row.num_conflict_files = metrics.num_conflict_files
        pr_row.num_conflict_regions = metrics.num_conflict_hunks
        pr_row.conflict_lines = metrics.conflict_lines

    if regions:
        sizes = [int(x.get("total_region_lines") or 0) for x in regions]
        pr_row.max_region_lines = max(sizes) if sizes else None
        pr_row.mean_region_lines = (sum(sizes) / len(sizes)) if sizes else None

    pr_rows.append(to_dict(pr_row))

    runlog_rows.append({
        "run_id": run_id,
        "extracted_at": EXTRACTED_AT,
        "pipeline_version": PIPELINE_VERSION,
        "pr_key": pr_key,
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "base_oid": pr_row.base_oid,
        "head_oid": pr_row.head_oid,
        "base_sim_oid": pr_row.base_sim_oid,
        "head_sim_oid": pr_row.head_sim_oid,
        "simulation_mode": pr_row.simulation_mode,
        "simulation_anchor_time": pr_row.simulation_anchor_time,
        "status_code": pr_row.status_code,
        "error_class": pr_row.error_class,
        "error_message_trunc": pr_row.error_message_trunc,
    })

    # ------------------------------------------------------------------
    # Step 6: Conflict-file table + file-level attribution
    # ------------------------------------------------------------------
    if conflict_files:
        counts: Dict[str, Dict[str, int]] = {}
        for reg in regions:
            fp = reg.get("file_path")
            if not fp:
                continue
            counts.setdefault(fp, {"num_regions_in_file": 0, "conflict_lines_in_file": 0})
            counts[fp]["num_regions_in_file"] += 1
            counts[fp]["conflict_lines_in_file"] += int(reg.get("total_region_lines") or 0)

        for fp in conflict_files:
            file_ext = ("." + fp.split(".")[-1].lower()) if "." in fp else ""
            ctype, stage_mask = conflict_type_for_path(repo_path, fp)

            conflict_file_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "agent": agent,
                "base_oid": pr_row.base_sim_oid,
                "head_oid": pr_row.head_sim_oid,
                "file_path": fp,
                "file_ext": file_ext,
                "num_regions_in_file": counts.get(fp, {}).get("num_regions_in_file", 0),
                "conflict_lines_in_file": counts.get(fp, {}).get("conflict_lines_in_file", 0),
                "conflict_type": ctype,
                "conflict_stage_mask": stage_mask,
            })

            # Attribution uses the original available base/head OIDs for "last touch"
            head_touch = last_touch_commit(repo_path, pr_row.head_oid, fp)
            base_touch = last_touch_commit(repo_path, pr_row.base_oid, fp)
            conflict_file_commit_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "agent": agent,
                "base_oid": pr_row.base_sim_oid,
                "head_oid": pr_row.head_sim_oid,
                "file_path": fp,
                "file_ext": file_ext,
                "head_last_touch_oid": head_touch,
                "base_last_touch_oid": base_touch,
                "attribution_method": "git_log_last_touch",
            })

    # ------------------------------------------------------------------
    # Step 7: Region table
    # ------------------------------------------------------------------
    if regions:
        for reg in regions:
            fp = reg.get("file_path")
            if not fp:
                continue

            file_ext = ("." + fp.split(".")[-1].lower()) if "." in fp else ""
            region_id = f"{pr_key}:{fp}:{reg.get('conflict_index')}"

            region_rows.append({
                "run_id": run_id,
                "extracted_at": EXTRACTED_AT,
                "pipeline_version": PIPELINE_VERSION,
                "region_id": region_id,
                "pr_key": pr_key,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "agent": agent,
                "base_oid": pr_row.base_sim_oid,
                "head_oid": pr_row.head_sim_oid,
                "file_path": fp,
                "file_ext": file_ext,
                "conflict_index": reg.get("conflict_index"),
                "start_line": reg.get("start_line"),
                "mid_line": reg.get("mid_line"),
                "end_line": reg.get("end_line"),
                "ours_lines": reg.get("ours_lines"),
                "theirs_lines": reg.get("theirs_lines"),
                "total_region_lines": reg.get("total_region_lines"),
                "ours_sha256": reg.get("ours_sha256"),
                "theirs_sha256": reg.get("theirs_sha256"),
                "ours_preview": reg.get("ours_preview"),
                "theirs_preview": reg.get("theirs_preview"),
                "ours_text": reg.get("ours_text"),
                "theirs_text": reg.get("theirs_text"),
            })

    return (
        pd.DataFrame(pr_rows),
        pd.DataFrame(region_rows),
        pd.DataFrame(conflict_file_rows),
        pd.DataFrame(list(repo_rows_by_repo.values())),
        pd.DataFrame(runlog_rows),
        pd.DataFrame(conflict_file_commit_rows),
    )


def extract_all(
    raw_df: pd.DataFrame,
    gh: GitHubTokenPool,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Backward-compatible batch mode. Useful for small runs, but main.py
    should prefer extract_one() for checkpoint/resume behavior.
    """
    run_id = str(uuid4())
    prs = prepare_prs(raw_df)

    if MAX_PRS > 0:
        prs = prs.head(MAX_PRS).copy()

    pr_parts = []
    region_parts = []
    cfile_parts = []
    repo_parts = []
    runlog_parts = []
    cfile_commit_parts = []

    for r in tqdm(prs.to_dict(orient="records"), total=len(prs)):
        pr_df, regions_df, conflict_files_df, repo_df, runlog_df, conflict_file_commits_df = extract_one(r, gh, run_id)
        pr_parts.append(pr_df)
        region_parts.append(regions_df)
        cfile_parts.append(conflict_files_df)
        repo_parts.append(repo_df)
        runlog_parts.append(runlog_df)
        cfile_commit_parts.append(conflict_file_commits_df)

    return (
        pd.concat(pr_parts, ignore_index=True) if pr_parts else pd.DataFrame(),
        pd.concat(region_parts, ignore_index=True) if region_parts else pd.DataFrame(),
        pd.concat(cfile_parts, ignore_index=True) if cfile_parts else pd.DataFrame(),
        pd.concat(repo_parts, ignore_index=True).drop_duplicates(subset=["repo_full_name"]) if repo_parts else pd.DataFrame(),
        pd.concat(runlog_parts, ignore_index=True) if runlog_parts else pd.DataFrame(),
        pd.concat(cfile_commit_parts, ignore_index=True) if cfile_commit_parts else pd.DataFrame(),
    )