"""Data schema for AgenticFlict pipeline output rows."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class PRRow:
    """Mutable container for all fields written to the PR-level output table.

    Populated incrementally during :func:`extractor.extract_one` as data
    becomes available at each pipeline step. Every field maps directly to a
    column in ``agenticflict_pr_{version}.csv``.

    Attributes:
        run_id: UUID identifying the pipeline run that produced this row.
        extracted_at: ISO 8601 UTC timestamp of extraction.
        pipeline_version: Value of :data:`config.PIPELINE_VERSION`.
        pr_key: Canonical identifier ``{repo_full_name}#{pr_number}``.
        repo_full_name: GitHub repository slug (``owner/repo``).
        pr_number: Pull request number within the repository.
        agent: AI coding agent that authored the PR.
        gh_state: GitHub PR state at extraction time (``OPEN`` or ``CLOSED``).
        gh_mergeable_at_extraction: GitHub ``mergeable`` field value at
            extraction time.
        created_at: ISO 8601 PR creation timestamp.
        closed_at: ISO 8601 PR closure timestamp.
        merged_at: ISO 8601 PR merge timestamp; ``None`` for unmerged PRs.
        pr_additions: Lines added by the PR.
        pr_deletions: Lines deleted by the PR.
        pr_changed_files: Number of files changed.
        pr_commits: Total commit count.
        base_ref_name: Name of the base branch.
        head_ref_name: Name of the head branch.
        base_oid: Base commit SHA as reported by GitHub.
        head_oid: Head commit SHA as reported by GitHub.
        merge_commit_oid: Merge commit SHA (merged PRs only).
        simulation_mode: Anchor strategy: ``"open_current"`` or
            ``"closed_base_at_close"``.
        simulation_anchor_time: ISO 8601 timestamp of the simulation anchor.
        base_sim_oid: Base commit SHA used for the merge simulation.
        head_sim_oid: Head commit SHA used for the merge simulation.
        conflict_label: ``True`` if simulation produced a textual conflict.
        num_conflict_files: Number of files with conflicts.
        num_conflict_regions: Total conflict regions across all files.
        conflict_lines: Total lines enclosed by conflict markers.
        max_region_lines: Lines in the largest single conflict region.
        mean_region_lines: Mean lines per conflict region.
        status_code: Pipeline outcome code, e.g. ``OK_CONFLICT`` or
            ``ERR_GH_API``.
        error_class: Coarse error category from :func:`extractor._err_class`.
        error_message_trunc: Truncated error message (max 300 chars).
    """
    # keys
    run_id: str
    extracted_at: str
    pipeline_version: str

    pr_key: str
    repo_full_name: str
    pr_number: int
    agent: Optional[str]

    # GitHub PR fields
    gh_state: Optional[str] = None
    gh_mergeable_at_extraction: Optional[str] = None
    created_at: Optional[str] = None
    closed_at: Optional[str] = None
    merged_at: Optional[str] = None

    pr_additions: Optional[int] = None
    pr_deletions: Optional[int] = None
    pr_changed_files: Optional[int] = None
    pr_commits: Optional[int] = None

    base_ref_name: Optional[str] = None
    head_ref_name: Optional[str] = None
    base_oid: Optional[str] = None
    head_oid: Optional[str] = None
    merge_commit_oid: Optional[str] = None



    # simulation anchors
    simulation_mode: Optional[str] = None
    simulation_anchor_time: Optional[str] = None
    base_sim_oid: Optional[str] = None
    head_sim_oid: Optional[str] = None

    # local merge label + metrics
    conflict_label: Optional[bool] = None
    num_conflict_files: Optional[int] = None
    num_conflict_regions: Optional[int] = None
    conflict_lines: Optional[int] = None
    max_region_lines: Optional[int] = None
    mean_region_lines: Optional[float] = None

    # status/provenance
    status_code: str = "UNKNOWN"
    error_class: str = ""
    error_message_trunc: str = ""

def to_dict(x) -> Dict[str, Any]:
    """Convert a dataclass instance to a plain dictionary.

    Args:
        x: Any dataclass instance (intended for :class:`PRRow`).

    Returns:
        Dictionary mapping field names to their values.
    """
    return asdict(x)
