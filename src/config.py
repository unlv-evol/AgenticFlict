"""Runtime configuration for the AgenticFlict extraction pipeline.

All settings are loaded from environment variables. A ``.env`` file in
the repository root is picked up automatically via ``python-dotenv``, so
exporting variables there is equivalent to setting them in the shell.

Environment Variables:
    HF_DATASET_NAME: HuggingFace dataset identifier (default: ``hao-li/AIDev``).
    HF_CONFIG: Optional dataset configuration name.
    HF_SPLIT: Dataset split to load (default: ``train``).
    HF_LIMIT: Maximum PR rows to load; ``0`` means no limit.
    HF_PARQUET_PATH: Path to a local Parquet file; takes precedence over HF Hub.
    HF_PARQUET_ENGINE: Parquet engine to use (default: ``pyarrow``).
    HF_TOKEN: HuggingFace API token for gated datasets.
    GITHUB_TOKENS: Comma-separated GitHub personal access tokens.
    MAX_PRS: Hard cap on PRs processed per run; ``0`` means no limit (default: ``200000``).
    GIT_TIMEOUT: Per-command Git subprocess timeout in seconds (default: ``120``).
    RETRY_SLEEP_SECS: Seconds between GitHub API retry attempts (default: ``3``).
    SECONDARY_RATE_SLEEP_SECS: Seconds to wait after a secondary rate-limit response (default: ``30``).
    MAX_API_RETRIES: Maximum GitHub API retry attempts per request (default: ``25``).
    REPO_CACHE_DIR: Directory for cached repository clones (default: ``./repo_cache``).
    OUT_DIR: Directory for Parquet output files (default: ``./out``).
    PIPELINE_VERSION: Provenance tag written to every output row (default: ``dev``).
    STORE_CONFLICT_TEXT: Set to ``1`` to store full conflict text in the regions table.
    CONFLICT_TEXT_PREVIEW_LINES: Lines to include in conflict text previews (default: ``5``).
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, timezone

HF_DATASET_NAME = os.environ.get("HF_DATASET_NAME", "hao-li/AIDev")
HF_CONFIG = os.environ.get("HF_CONFIG", "")
HF_SPLIT = os.environ.get("HF_SPLIT", "train")
HF_LIMIT = int(os.environ.get("HF_LIMIT", "0"))
HF_PARQUET_PATH = os.environ.get("HF_PARQUET_PATH", "")
HF_PARQUET_ENGINE = os.environ.get("HF_PARQUET_ENGINE", "pyarrow")
HF_TOKEN = os.environ.get("HF_TOKEN", "")


GITHUB_TOKENS = [t.strip() for t in os.environ.get("GITHUB_TOKENS", "").split(",") if t.strip()]

MAX_PRS = int(os.environ.get("MAX_PRS", "200000"))
GIT_TIMEOUT = int(os.environ.get("GIT_TIMEOUT", "120"))

# GitHub API backoff controls
RETRY_SLEEP_SECS = int(os.environ.get("RETRY_SLEEP_SECS", "3"))
SECONDARY_RATE_SLEEP_SECS = int(os.environ.get("SECONDARY_RATE_SLEEP_SECS", "30"))
MAX_API_RETRIES = int(os.environ.get("MAX_API_RETRIES", "25"))

REPO_CACHE_DIR = os.environ.get("REPO_CACHE_DIR", "./repo_cache")

# Base output directory
OUT_DIR = os.environ.get("OUT_DIR", "./out")
os.makedirs(OUT_DIR, exist_ok=True)

# OUT_PR = os.path.join(OUT_DIR, "agenticflict_pr.csv")
# OUT_REGIONS = os.path.join(OUT_DIR, "agenticflict_regions.csv")
# OUT_CONFLICT_FILES = os.path.join(OUT_DIR, "agenticflict_conflict_files.csv")
# OUT_CONFLICT_FILE_COMMITS = os.path.join(OUT_DIR, "agenticflict_conflict_file_commits.csv")
# OUT_REPO = os.path.join(OUT_DIR, "agenticflict_repo.csv")
# OUT_RUNLOG = os.path.join(OUT_DIR, "agenticflict_runlog.csv")
OUT_PR = os.path.join(OUT_DIR, "agentconflict_pr.parquet")
OUT_REGIONS = os.path.join(OUT_DIR, "agentconflict_regions.parquet")
OUT_CONFLICT_FILES = os.path.join(OUT_DIR, "agentconflict_conflict_files.parquet")
OUT_CONFLICT_FILE_COMMITS = os.path.join(OUT_DIR, "agentconflict_conflict_file_commits.parquet")
OUT_REPO = os.path.join(OUT_DIR, "agentconflict_repo.parquet")
OUT_RUNLOG = os.path.join(OUT_DIR, "agentconflict_runlog.parquet")

# Provenance
PIPELINE_VERSION = os.environ.get("PIPELINE_VERSION", "dev")
EXTRACTED_AT = datetime.now(timezone.utc).isoformat()

# Store conflict text
STORE_CONFLICT_TEXT = os.environ.get("STORE_CONFLICT_TEXT", "0") == "1"
CONFLICT_TEXT_PREVIEW_LINES = int(os.environ.get("CONFLICT_TEXT_PREVIEW_LINES", "5"))