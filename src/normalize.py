"""Utilities for normalising heterogeneous pull-request records.

The HuggingFace source dataset (``hao-li/AIDev``) may use different column
names across configurations and splits. This module provides regex-based
parsers that extract the three canonical fields required by the pipeline
(``repo_full_name``, ``pr_number``, ``agent``) regardless of which column
names are present in the raw data.
"""
from __future__ import annotations

import re
from typing import Dict, Any, Optional, List

import pandas as pd

RE_API_REPO = re.compile(r"/repos/([^/]+/[^/]+)")
RE_GH_REPO = re.compile(r"github\.com/([^/]+/[^/]+)")
RE_PR_URL = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")


def parse_repo_full_name_from_any(row: Dict[str, Any]) -> Optional[str]:
    """Extract an ``owner/repo`` slug from a PR record using multiple fallback strategies.

    Tries the following in order:

    1. Direct slug fields: ``repo_full_name``, ``full_name``, etc.
    2. Pull-request URL fields: ``html_url``, ``pull_request_url``, etc.
    3. GitHub API path fields: ``url``, ``repository_url``, etc.

    ``.git`` suffixes are stripped from all candidates.

    Args:
        row: Dict representing a single raw PR record.

    Returns:
        Normalised ``owner/repo`` slug, or ``None`` if no slug can be parsed.
    """
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
    """Infer a PR number from a raw PR record using multiple fallback strategies.

    Tries numeric fields first (``number``, ``pr_number``, etc.), then
    extracts the number from URL fields if needed.

    Args:
        row: Dict representing a single raw PR record.

    Returns:
        Pull request number as an integer, or ``None`` if it cannot be
        determined.
    """
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
    """Infer the AI coding agent name from a raw PR record.

    Checks ``agent``, ``tool``, ``autonomous_agent``, and ``agent_name``
    fields in order, returning the first non-empty string value found.

    Args:
        row: Dict representing a single raw PR record.

    Returns:
        Agent name string, or ``None`` if not found.
    """
    for k in ["agent", "tool", "autonomous_agent", "agent_name"]:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def normalize_prs(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise a raw PR DataFrame to the canonical three-column format.

    Applies :func:`parse_repo_full_name_from_any`, :func:`infer_pr_number`,
    and :func:`infer_agent` to every row and returns a new DataFrame with
    columns ``repo_full_name`` (string), ``pr_number`` (Int64), and
    ``agent`` (string).

    Args:
        df: Raw DataFrame as loaded by :func:`hf_loader.load_hf_split`.

    Returns:
        Normalised DataFrame with exactly three columns.
    """
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
