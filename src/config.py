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