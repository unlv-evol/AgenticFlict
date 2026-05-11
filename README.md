# AgenticFlict: A Large-Scale Dataset of Merge Conflicts in AI Coding Agent Pull Requests

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19396916.svg)](https://doi.org/10.5281/zenodo.19396916)
[![arXiv](https://img.shields.io/badge/arXiv-2604.03551-b31b1b.svg)](https://arxiv.org/abs/2604.03551)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

---

## Abstract

As AI coding agents proliferate on open-source platforms, their pull requests increasingly collide with concurrent human and agent contributions — yet the scale and nature of these conflicts remain unstudied. **AgenticFlict** is the first large-scale dataset of textual merge conflicts in AI agent-authored pull requests. It covers **107,026 simulated merges** across **59,412 repositories** and **5 distinct AI coding agents**, yielding **29,609 conflicting PRs** (27.67% conflict rate). Conflict detection is based on deterministic local merge simulation anchored at exact commit OIDs, making every label reproducible from public GitHub history. The dataset is organized as a relational schema spanning four granularities — pull request, file, conflict region, and repository — enabling studies of conflict prediction, agent behavior analysis, software evolution, and automated conflict resolution.

---

## Table of Contents

- [Motivation](#motivation)
- [Dataset Summary](#dataset-summary)
- [Research Use Cases](#research-use-cases)
- [Dataset Versions](#dataset-versions)
- [Schema and File Descriptions](#schema-and-file-descriptions)
- [Quickstart](#quickstart)
- [Reproducing the Dataset](#reproducing-the-dataset)
- [Directory Structure](#directory-structure)
- [Limitations](#limitations)
- [License and Data Representation](#license-and-data-representation)
- [Citation](#citation)
- [Contact](#contact)

---

## Motivation

AI coding agents such as Devin, SWE-agent, and AutoCodeRover autonomously submit pull requests to public repositories at scale. Unlike individual human contributors, these agents operate concurrently, often targeting the same files and functions, creating a new and underexplored source of merge conflicts. Understanding the frequency, distribution, and structure of these conflicts is essential for:

- Researchers studying AI-assisted software development workflows
- Tool builders developing conflict-aware agents or automated resolution pipelines
- Repository maintainers seeking to model integration risk from AI-generated contributions
- Empiricists investigating how agent behavior differs across programming languages, repository characteristics, and PR size

AgenticFlict provides the infrastructure — labeled data, fine-grained conflict metadata, and a reproducible extraction pipeline — to pursue these questions at scale.

---

## Dataset Summary

| Metric | Value |
|---|---|
| Total PRs identified | 142,652 |
| Successfully simulated PRs | 107,026 |
| Conflicting PRs | 29,609 |
| Conflict rate | 27.67% |
| Distinct repositories | 59,412 |
| AI coding agents covered | 5 |
| Granularities available | PR · File · Region · Repo |

The 27.67% conflict rate is notably higher than rates reported in prior studies of human-authored PRs (typically 10–20%), suggesting that agent-generated contributions carry elevated integration risk.

---

## Research Use Cases

AgenticFlict is designed to support — but is not limited to — the following research directions:

**Conflict prediction**  
Train classifiers that predict whether an incoming agent PR will conflict, using PR size, repository activity, file overlap, and agent identity as features.

**Agent behavior comparison**  
Compare conflict profiles (rate, severity, conflict type) across the 5 included AI agents to identify behavioral patterns that elevate integration risk.

**Conflict resolution**  
Use paired conflict-region data (including SHA-256 hashes of both sides of each conflict) as inputs to automated resolution models.

**Software repository mining**  
Study how repository characteristics — language, stars, fork count, default branch policy — moderate conflict likelihood in AI-authored contributions.

**Longitudinal and temporal analysis**  
Use `created_at` and `closed_at` timestamps to analyze how agent deployment patterns and conflict rates have changed over time.

---

## Dataset Versions

The dataset is hosted on Zenodo: **[https://doi.org/10.5281/zenodo.19396916](https://doi.org/10.5281/zenodo.19396916)**

### CLEAN Dataset (Recommended for analysis)

The CLEAN version is designed for analysis and modeling. It:

- Retains only analysis-relevant attributes
- Removes pipeline metadata (`run_id`, timestamps, debug fields)
- Excludes raw source code content for licensing compliance
- Guarantees a consistent schema across all tables

> All results in the associated paper are based on the CLEAN dataset unless explicitly noted.

### RAW Dataset (Recommended for reproducibility)

The RAW version contains the full output of the extraction pipeline:

- Pipeline metadata (`run_id`, `anchor_time`, simulation parameters)
- Intermediate states and simulation mode flags
- Execution logs and error classification
- Optional short conflict-text previews (configurable at extraction time)

A complete field-level mapping between versions is provided in `raw_to_clean_manifest.csv` (included in the Zenodo archive).

---

## Schema and File Descriptions

All tables are linked through a single canonical identifier:

```
pr_key = {repo_full_name}#{pr_number}
```

where `repo_full_name` follows the GitHub `owner/repository` convention.

### `agenticflict_pr_{version}.csv` — Pull Request Level

The primary table. One row per simulated PR.

| Column | Type | Description |
|---|---|---|
| `pr_key` | string | Canonical identifier (`owner/repo#number`) |
| `repo_full_name` | string | GitHub repository slug |
| `pr_number` | int | PR number within the repository |
| `agent` | string | AI coding agent that authored the PR |
| `conflict_label` | bool | `True` if merge simulation produced a textual conflict |
| `num_conflict_files` | int | Number of files with conflicts |
| `num_conflict_regions` | int | Total conflict regions across all files |
| `total_conflict_lines` | int | Sum of conflict-marker-bounded lines |
| `max_region_lines` | int | Lines in the largest single conflict region |
| `mean_region_lines` | float | Mean lines per conflict region |
| `simulation_mode` | string | `open` or `closed_unmerged` |
| `base_oid` | string | Base commit SHA used for simulation |
| `head_oid` | string | Head commit SHA used for simulation |
| `pr_state` | string | GitHub PR state (`OPEN` / `CLOSED`) |
| `additions` | int | Lines added in the PR |
| `deletions` | int | Lines deleted in the PR |
| `changed_files` | int | Files changed in the PR |
| `created_at` | datetime | PR creation timestamp |
| `closed_at` | datetime | PR closure timestamp (if closed) |

### `agenticflict_conflict_files_{version}.csv` — File Level

One row per file involved in a conflict within a conflicting PR.

| Column | Type | Description |
|---|---|---|
| `pr_key` | string | Foreign key to PR table |
| `file_path` | string | Relative path of the conflicting file |
| `conflict_type` | string | Git 3-way merge classification (e.g., `both_modified`, `both_added`) |
| `num_regions` | int | Number of conflict regions in this file |
| `total_lines` | int | Total conflict-bounded lines in this file |
| `last_touch_commit` | string | SHA of last commit to touch this file on the base branch |

### `agenticflict_regions_{version}.csv` — Conflict Region Level

One row per conflict region (delimited by `<<<<<<<` / `=======` / `>>>>>>>` markers).

| Column | Type | Description |
|---|---|---|
| `pr_key` | string | Foreign key to PR table |
| `file_path` | string | File containing this region |
| `region_index` | int | 0-based index of region within the file |
| `start_line` | int | Line number of `<<<<<<<` marker |
| `mid_line` | int | Line number of `=======` marker |
| `end_line` | int | Line number of `>>>>>>>` marker |
| `ours_lines` | int | Lines on the `ours` (base) side |
| `theirs_lines` | int | Lines on the `theirs` (incoming) side |
| `total_lines` | int | `ours_lines + theirs_lines` |
| `ours_hash` | string | SHA-256 of the `ours` conflict block |
| `theirs_hash` | string | SHA-256 of the `theirs` conflict block |

### `agenticflict_conflict_file_commits_{version}.csv` — Commit Attribution

Maps conflicting files to the last commit that touched them on the base branch, supporting blame-style analysis.

| Column | Type | Description |
|---|---|---|
| `pr_key` | string | Foreign key to PR table |
| `file_path` | string | Conflicting file path |
| `commit_sha` | string | SHA of the last base-branch commit touching this file |

### `agenticflict_repo_{version}.csv` — Repository Level

One row per distinct repository in the dataset.

| Column | Type | Description |
|---|---|---|
| `repo_full_name` | string | GitHub repository slug |
| `default_branch` | string | Default branch name |
| `primary_language` | string | Detected primary programming language |
| `stargazer_count` | int | Stars at time of extraction |
| `fork_count` | int | Forks at time of extraction |
| `is_fork` | bool | Whether the repository is itself a fork |
| `is_archived` | bool | Whether the repository is archived |

### `agenticflict_runlog.csv` — Execution Log (RAW only)

One row per pipeline execution attempt. Useful for auditing extraction failures and simulation skips.

---

## Quickstart

### 1. Download the dataset

```bash
# Download directly from Zenodo
wget https://zenodo.org/records/19396916/files/agenticflict_clean.zip
unzip agenticflict_clean.zip -d data/
```

Or visit **[https://doi.org/10.5281/zenodo.19396916](https://doi.org/10.5281/zenodo.19396916)** to download manually.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Load the dataset

```python
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/clean")

pr      = pd.read_csv(DATA_DIR / "agenticflict_pr_clean.csv")
files   = pd.read_csv(DATA_DIR / "agenticflict_conflict_files_clean.csv")
regions = pd.read_csv(DATA_DIR / "agenticflict_regions_clean.csv")
repos   = pd.read_csv(DATA_DIR / "agenticflict_repo_clean.csv")
commits = pd.read_csv(DATA_DIR / "agenticflict_conflict_file_commits_clean.csv")

print(f"PRs: {len(pr):,}  |  Conflicting: {pr['conflict_label'].sum():,}  |  Conflict rate: {pr['conflict_label'].mean():.1%}")
```

### Conflict rate by AI agent

```python
agent_stats = (
    pr.groupby("agent")["conflict_label"]
    .agg(total="count", conflicts="sum")
    .assign(conflict_rate=lambda d: d["conflicts"] / d["total"])
    .sort_values("conflict_rate", ascending=False)
)
print(agent_stats)
```

### Join PR metadata with conflict regions

```python
merged = regions.merge(pr[["pr_key", "agent", "repo_full_name"]], on="pr_key")
print(merged.groupby("agent")["total_lines"].describe())
```

---

## Reproducing the Dataset

The extraction pipeline is fully deterministic given access to public GitHub history.

### How it works

1. **Source PRs** are loaded from the [AIDev HuggingFace dataset](https://huggingface.co/datasets/hao-li/AIDev), which catalogs AI agent-authored PRs.
2. **Metadata** is fetched via the GitHub GraphQL API (PR state, commit OIDs, repository attributes).
3. **Repositories** are cloned locally using shallow blob-filter clones for efficiency and cached on disk.
4. **Simulation anchors** are determined per PR:
   - `OPEN` PRs: current `base` and `head` commits
   - `CLOSED` (unmerged) PRs: base branch state at closure time
5. **Merge simulation** executes `git merge` locally using the anchored OIDs.
6. **Conflict extraction** parses `<<<<<<<`/`=======`/`>>>>>>>` markers and computes line-level metrics and SHA-256 hashes.

### Running the pipeline

```bash
cp .env-example .env
# Edit .env: add your GitHub token(s) and configure HF dataset settings

python src/main.py
```

Multiple GitHub tokens are supported via `GITHUB_TOKENS` (comma-separated) and are rotated automatically to distribute API rate limits.

### Verifying a single label

Each PR row stores `base_oid` and `head_oid`. Given those two commit SHAs and repository access, any label can be independently verified:

```bash
git clone https://github.com/{owner}/{repo} /tmp/verify-repo
cd /tmp/verify-repo
git fetch origin {head_oid}
git checkout {base_oid}
git merge --no-commit --no-ff {head_oid}
# Non-zero exit + conflict markers confirm a conflicting PR
```

---

## Directory Structure

```
AgenticFlict/
├── analysis/
│   └── 001_exploratory_analysis.ipynb
├── figures/
│   ├── Fig1_conflict_rate_by_agent.pdf
│   ├── Fig2_conflict_severity_by_agent.pdf
│   └── Fig_conflict_rate_by_pr_size.pdf
├── src/
│   ├── main.py
│   ├── config.py
│   ├── extractor.py
│   ├── git_ops.py
│   ├── github_client.py
│   ├── schema.py
│   ├── normalize.py
│   └── hf_loader.py
├── requirements.txt
├── .env-example
├── online-appendix.pdf
└── README.md
```

The dataset files themselves are hosted on Zenodo at **[https://doi.org/10.5281/zenodo.19396916](https://doi.org/10.5281/zenodo.19396916)** and are not tracked in this repository.

---

## Limitations

- **Textual conflicts only.** The dataset captures syntactic merge conflicts as reported by Git's 3-way merge. Semantic conflicts (syntactically correct but behaviorally incompatible changes) are not detected.
- **Excluded PRs.** PRs are excluded when repositories are deleted, made private, or inaccessible at extraction time, introducing potential survivorship bias toward more active repositories.
- **No human-authored baseline.** The current version focuses exclusively on AI agent PRs. A matched human-authored baseline will be added in a future release to enable direct comparison.
- **Snapshot in time.** Conflict labels for `OPEN` PRs reflect repository state at extraction time. Re-running the pipeline later may yield different results as base branches advance.
- **Agent coverage.** Coverage is limited to agents represented in the AIDev source dataset (5 agents). Agents with few PRs may exhibit higher variance in per-agent metrics.

---

## License and Data Representation

This repository and dataset are released under the [MIT License](LICENSE).

To comply with GitHub Terms of Service, **no raw source code is stored**. The dataset represents conflict content through:

- **Cryptographic hashes** (`ours_hash`, `theirs_hash`) — SHA-256 digests of each conflict block, usable for deduplication and similarity analysis without storing code.
- **Short text previews** — available only in the RAW dataset and configurable at extraction time.

Repository metadata (stars, forks, language) reflects values at extraction time and may differ from current repository state.

---

## Citation

If you use AgenticFlict in your research, please cite both the dataset and the companion paper:

```bibtex
@dataset{agenticflict2026,
  title     = {{AgenticFlict}: A Large-Scale Dataset of Merge Conflicts in {AI} Coding Agent Pull Requests},
  author    = {Ogenrwot, Daniel and {UNLV EVOL Lab}},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19396916},
  url       = {https://doi.org/10.5281/zenodo.19396916}
}

@article{agenticflict2026paper,
  title   = {{AgenticFlict}: A Large-Scale Dataset of Merge Conflicts in {AI} Coding Agent Pull Requests},
  author  = {Ogenrwot, Daniel and {UNLV EVOL Lab}},
  year    = {2026},
  journal = {arXiv preprint arXiv:2604.03551},
  url     = {https://arxiv.org/abs/2604.03551}
}
```

---

## Contact

**UNLV EVOL Lab** — University of Nevada, Las Vegas  
Questions, issues, and collaboration inquiries: open an [issue](../../issues) or refer to the contact information in the [companion paper](https://arxiv.org/abs/2604.03551).
