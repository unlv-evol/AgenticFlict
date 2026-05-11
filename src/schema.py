from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class PRRow:
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
    return asdict(x)
