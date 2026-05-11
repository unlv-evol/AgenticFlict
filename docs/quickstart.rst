Quickstart
==========

Using the dataset
-----------------

The dataset is hosted on Zenodo. Download it before running any of the
examples below.

.. code-block:: bash

   wget https://zenodo.org/records/19396916/files/agenticflict_clean.zip
   unzip agenticflict_clean.zip -d data/

Or visit `https://doi.org/10.5281/zenodo.19396916
<https://doi.org/10.5281/zenodo.19396916>`_ to download manually.

Load all tables
~~~~~~~~~~~~~~~

.. code-block:: python

   from pathlib import Path
   import pandas as pd

   DATA_DIR = Path("data/clean")

   pr      = pd.read_csv(DATA_DIR / "agenticflict_pr_clean.csv")
   files   = pd.read_csv(DATA_DIR / "agenticflict_conflict_files_clean.csv")
   regions = pd.read_csv(DATA_DIR / "agenticflict_regions_clean.csv")
   repos   = pd.read_csv(DATA_DIR / "agenticflict_repo_clean.csv")
   commits = pd.read_csv(DATA_DIR / "agenticflict_conflict_file_commits_clean.csv")

   print(
       f"PRs: {len(pr):,}  |  "
       f"Conflicting: {pr['conflict_label'].sum():,}  |  "
       f"Conflict rate: {pr['conflict_label'].mean():.1%}"
   )

Conflict rate by agent
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   agent_stats = (
       pr.groupby("agent")["conflict_label"]
       .agg(total="count", conflicts="sum")
       .assign(conflict_rate=lambda d: d["conflicts"] / d["total"])
       .sort_values("conflict_rate", ascending=False)
   )
   print(agent_stats)

Join PR metadata with conflict regions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   merged = regions.merge(pr[["pr_key", "agent", "repo_full_name"]], on="pr_key")
   print(merged.groupby("agent")["total_region_lines"].describe())

Running the extraction pipeline
--------------------------------

To re-run the pipeline from scratch or extend the dataset:

.. code-block:: bash

   cd src
   python main.py

The pipeline supports checkpoint/resume. If interrupted, re-running
``main.py`` will skip already-processed PRs. To retry previously errored
PRs, set ``RETRY_FAILED=1``:

.. code-block:: bash

   RETRY_FAILED=1 python main.py

Verifying a single conflict label
-----------------------------------

Each PR row stores ``base_oid`` and ``head_oid``. You can independently
verify any conflict label with plain Git:

.. code-block:: bash

   git clone https://github.com/{owner}/{repo} /tmp/verify-repo
   cd /tmp/verify-repo
   git fetch origin {head_oid}
   git checkout {base_oid}
   git merge --no-commit --no-ff {head_oid}
   # Non-zero exit + conflict markers confirm a conflicting PR
