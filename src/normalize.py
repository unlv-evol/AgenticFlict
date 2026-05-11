from __future__ import annotations

import re
from typing import Dict, Any, Optional, List

import pandas as pd

RE_API_REPO = re.compile(r"/repos/([^/]+/[^/]+)")
RE_GH_REPO = re.compile(r"github\.com/([^/]+/[^/]+)")
RE_PR_URL = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")


def parse_repo_full_name_from_any(row: Dict[str, Any]) -> Optional[str]:
    for k in ["repo_full_name", "full_name", "repository_full_name", "repository.full_name"]:
        v = row.get(k)
        if isinstance(v, str) and "/" in v:
            s = v.strip()
            s = re.sub(r"\.git$", "", s)
            return s

    for k in ["repo_url", "repository_url", "url", "html_url", "pull_request_url"]:
        v = row.get(k)
        if not isinstance(v, str):
            continue
        v = v.strip()

        m = RE_PR_URL.search(v)
        if m:
            return re.sub(r"\.git$", "", m.group(1))

        m = RE_API_REPO.search(v)
        if m:
            return re.sub(r"\.git$", "", m.group(1))

        m = RE_GH_REPO.search(v)
        if m:
            return re.sub(r"\.git$", "", m.group(1))

    return None


def infer_pr_number(row: Dict[str, Any]) -> Optional[int]:
    for k in ["number", "pr_number", "pull_number", "pull_request_number"]:
        v = row.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            pass

    for k in ["html_url", "pull_request_url", "url"]:
        v = row.get(k)
        if isinstance(v, str):
            m = RE_PR_URL.search(v)
            if m:
                return int(m.group(2))

    return None


def infer_agent(row: Dict[str, Any]) -> Optional[str]:
    for k in ["agent", "tool", "autonomous_agent", "agent_name"]:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def normalize_prs(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for r in df.to_dict(orient="records"):
        rows.append({
            "repo_full_name": parse_repo_full_name_from_any(r),
            "pr_number": infer_pr_number(r),
            "agent": infer_agent(r),
        })

    out = pd.DataFrame(rows)
    out["repo_full_name"] = out["repo_full_name"].astype("string")
    out["pr_number"] = pd.to_numeric(out["pr_number"], errors="coerce").astype("Int64")
    out["agent"] = out["agent"].astype("string")

    return out
