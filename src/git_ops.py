from __future__ import annotations

import os
import hashlib
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any

from config import REPO_CACHE_DIR, GIT_TIMEOUT, STORE_CONFLICT_TEXT, CONFLICT_TEXT_PREVIEW_LINES


def run(cmd: List[str], cwd: Optional[str] = None, timeout: int = GIT_TIMEOUT) -> Tuple[int, str, str]:
    """Run a subprocess command and return its output.

    Args:
        cmd: Command and arguments as a list, e.g. ``["git", "status"]``.
        cwd: Working directory for the subprocess. Defaults to the current
            directory.
        timeout: Maximum seconds to wait before raising
            :exc:`subprocess.TimeoutExpired`.

    Returns:
        A 3-tuple ``(returncode, stdout, stderr)``.
    """
    p = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr


def repo_dir_for(full_name: str) -> str:
    """Return the local cache path for a GitHub repository.

    The path combines the repository slug with a short SHA-1 hash of the
    slug to avoid filesystem collisions on case-insensitive systems.

    Args:
        full_name: GitHub repository slug, e.g. ``"owner/repo"``.

    Returns:
        Absolute path inside :data:`config.REPO_CACHE_DIR`.
    """
    h = hashlib.sha1(full_name.encode("utf-8")).hexdigest()[:12]
    safe_name = full_name.replace("/", "__")
    return os.path.join(REPO_CACHE_DIR, f"{safe_name}__{h}")


def ensure_repo(full_name: str) -> str:
    """Clone a repository if not cached, then fetch all remotes.

    Uses ``--filter=blob:none --no-checkout`` for a blobless clone that
    downloads only the commit graph, keeping disk usage minimal.

    Args:
        full_name: GitHub repository slug, e.g. ``"owner/repo"``.

    Returns:
        Absolute path to the local repository.

    Raises:
        RuntimeError: If cloning or fetching fails.
    """
    os.makedirs(REPO_CACHE_DIR, exist_ok=True)
    path = repo_dir_for(full_name)

    if not os.path.exists(path):
        url = f"https://github.com/{full_name}.git"
        rc, _, err = run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", url, path],
            timeout=GIT_TIMEOUT * 3,
        )
        if rc != 0:
            raise RuntimeError(f"clone failed for {full_name}: {err.strip()}")

    rc, _, err = run(["git", "fetch", "--all", "--prune"], cwd=path, timeout=GIT_TIMEOUT * 3)
    if rc != 0:
        raise RuntimeError(f"fetch failed for {full_name}: {err.strip()}")

    return path


def resolve_base_oid_before(repo_path: str, ref_name: str, before_iso: str) -> Optional[str]:
    """
    Resolve the latest commit reachable from origin/<ref_name> before a timestamp.
    Used for closed-unmerged PRs when simulating against the base branch state
    at PR closure time.
    """
    if not ref_name or not before_iso:
        return None

    ref = f"origin/{ref_name}"
    rc, out, _ = run(["git", "rev-list", "-1", f"--before={before_iso}", ref], cwd=repo_path)
    sha = out.strip() if rc == 0 else ""
    return sha if sha else None


@dataclass
class ConflictMetrics:
    """Summary statistics for a single merge simulation.

    Attributes:
        has_text_conflict: ``True`` if the merge produced at least one
            textual conflict marker.
        num_conflict_files: Number of files containing conflict markers.
        num_conflict_markers: Total ``<<<<<<<`` markers found across all
            files (equal to ``num_conflict_hunks``).
        num_conflict_hunks: Total conflict regions across all files.
        conflict_lines: Total lines enclosed by conflict markers.
    """
    has_text_conflict: bool
    num_conflict_files: int = 0
    num_conflict_markers: int = 0
    num_conflict_hunks: int = 0
    conflict_lines: int = 0


def list_conflicting_files(repo_path: str) -> List[str]:
    """List files with unresolved conflicts in the working tree.

    Runs ``git diff --name-only --diff-filter=U`` to find files in the
    unmerged (``U``) state after a failed ``git merge``.

    Args:
        repo_path: Path to the local Git repository.

    Returns:
        List of relative file paths that contain conflict markers.
    """
    rc, out, _ = run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=repo_path)
    if rc != 0:
        return []
    return [f.strip() for f in out.splitlines() if f.strip()]


def _unmerged_stage_mask(repo_path: str, file_path: str) -> int:
    """
    Return bitmask of unmerged index stages present for file_path.
    Bit i is set if stage i exists (i in {1,2,3}).
    """
    rc, out, _ = run(["git", "ls-files", "-u", "--", file_path], cwd=repo_path)
    if rc != 0 or not out.strip():
        return 0
    mask = 0
    for line in out.splitlines():
        parts = line.strip().split()
        if len(parts) < 3:
            continue
        try:
            stage = int(parts[2])
        except Exception:
            continue
        if stage in (1, 2, 3):
            mask |= (1 << stage)
    return mask


def conflict_type_for_path(repo_path: str, file_path: str) -> Tuple[str, str]:
    """
    Classify file-level conflict type using Git's unmerged index stages.
    Returns: (conflict_type, stage_mask_str)
    """
    mask = _unmerged_stage_mask(repo_path, file_path)
    has_base = bool(mask & (1 << 1))
    has_ours = bool(mask & (1 << 2))
    has_theirs = bool(mask & (1 << 3))

    stages = []
    if has_base:
        stages.append("1")
    if has_ours:
        stages.append("2")
    if has_theirs:
        stages.append("3")
    mask_str = "|".join(stages) if stages else ""

    if has_ours and has_theirs:
        if not has_base:
            return "both_added", mask_str
        return "both_modified", mask_str

    if has_ours and not has_theirs:
        if not has_base:
            return "added_by_us", mask_str
        return "deleted_by_them", mask_str

    if not has_ours and has_theirs:
        if not has_base:
            return "added_by_them", mask_str
        return "deleted_by_us", mask_str

    return "unknown", mask_str


def last_touch_commit(repo_path: str, rev: str, file_path: str) -> Optional[str]:
    """Return the SHA of the last commit that touched a file at a given revision.

    Args:
        repo_path: Path to the local Git repository.
        rev: Commit SHA or ref to start traversal from.
        file_path: Relative path to the file within the repository.

    Returns:
        Full commit SHA string, or ``None`` if the file has no history at
        ``rev``.
    """
    rc, out, _ = run(["git", "log", "-n", "1", "--format=%H", rev, "--", file_path], cwd=repo_path)
    sha = out.strip() if rc == 0 else ""
    return sha if sha else None


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def extract_conflict_regions_from_text(
    text: str,
    store_text: bool = False,
    preview_lines: int = 5,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Parse conflict markers in file text and extract region-level data.

    Scans for ``<<<<<<<`` / ``=======`` / ``>>>>>>>`` conflict marker
    triplets and records line boundaries, line counts, SHA-256 hashes,
    and optional text previews for each conflict region.

    Args:
        text: Full text content of a conflicted file.
        store_text: When ``True``, include the full ``ours_text`` and
            ``theirs_text`` for each region (may be large).
        preview_lines: Number of lines to include in ``ours_preview``
            and ``theirs_preview`` fields.

    Returns:
        A 3-tuple ``(regions, marker_count, total_conflict_lines)`` where
        ``regions`` is a list of region dicts, ``marker_count`` is the
        number of conflict regions found, and ``total_conflict_lines`` is
        the cumulative line count across all regions.
    """
    lines = text.splitlines()
    regions: List[Dict[str, Any]] = []

    i = 0
    idx = 0
    total_conflict_lines = 0

    while i < len(lines):
        if lines[i].startswith("<<<<<<<"):
            start = i
            mid = None
            end = None

            j = i + 1
            while j < len(lines):
                if lines[j].startswith("=======") and mid is None:
                    mid = j
                elif lines[j].startswith(">>>>>>>"):
                    end = j
                    break
                j += 1

            if mid is not None and end is not None and start < mid < end:
                ours_chunk = "\n".join(lines[start + 1 : mid])
                theirs_chunk = "\n".join(lines[mid + 1 : end])

                ours_lines = mid - start - 1
                theirs_lines = end - mid - 1
                total_region_lines = end - start + 1
                total_conflict_lines += total_region_lines

                row = {
                    "conflict_index": idx,
                    "start_line": start + 1,
                    "mid_line": mid + 1,
                    "end_line": end + 1,
                    "ours_lines": ours_lines,
                    "theirs_lines": theirs_lines,
                    "total_region_lines": total_region_lines,
                    "ours_sha256": _sha256(ours_chunk),
                    "theirs_sha256": _sha256(theirs_chunk),
                    "ours_preview": "\n".join(ours_chunk.splitlines()[:preview_lines]),
                    "theirs_preview": "\n".join(theirs_chunk.splitlines()[:preview_lines]),
                }

                if store_text:
                    row["ours_text"] = ours_chunk
                    row["theirs_text"] = theirs_chunk

                regions.append(row)
                idx += 1
                i = end + 1
                continue

            i += 1
        else:
            i += 1

    marker_count = len(regions)
    return regions, marker_count, total_conflict_lines


def compute_conflict_details(repo_path: str, files: List[str]) -> Tuple[List[Dict[str, Any]], ConflictMetrics]:
    """Compute conflict region data and summary metrics for a list of conflicted files.

    Reads each file from disk, calls :func:`extract_conflict_regions_from_text`,
    and aggregates results across all files.

    Args:
        repo_path: Path to the local Git repository.
        files: List of relative file paths known to be in conflict.

    Returns:
        A 2-tuple ``(regions, metrics)`` where ``regions`` is a flat list
        of region dicts (each augmented with ``"file_path"``) and ``metrics``
        is a :class:`ConflictMetrics` instance with aggregate counts.
    """
    all_regions: List[Dict[str, Any]] = []
    total_markers = 0
    total_lines = 0

    for f in files:
        fp = os.path.join(repo_path, f)
        if not os.path.exists(fp):
            continue

        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
        except Exception:
            continue

        regions, marker_count, conflict_lines = extract_conflict_regions_from_text(
            txt,
            store_text=STORE_CONFLICT_TEXT,
            preview_lines=CONFLICT_TEXT_PREVIEW_LINES,
        )

        total_markers += marker_count
        total_lines += conflict_lines

        for r in regions:
            all_regions.append({"file_path": f, **r})

    metrics = ConflictMetrics(
        has_text_conflict=(len(files) > 0),
        num_conflict_files=len(files),
        num_conflict_markers=total_markers,
        num_conflict_hunks=total_markers,
        conflict_lines=total_lines,
    )
    return all_regions, metrics


def merge_test(
    repo_path: str,
    base_oid: str,
    head_oid: str,
) -> Tuple[bool, Optional[ConflictMetrics], List[Dict[str, Any]], List[str], str]:
    """Perform a deterministic local merge simulation.

    Checks out ``base_oid`` on a temporary branch and attempts
    ``git merge --no-commit --no-ff head_oid``. The working tree is
    always cleaned up (merge aborted) before returning.

    Args:
        repo_path: Path to the local Git repository.
        base_oid: Commit SHA to use as the merge base.
        head_oid: Commit SHA of the incoming branch.

    Returns:
        A 5-tuple ``(clean, metrics, regions, conflict_files, detail)``
        where:

        - ``clean`` is ``True`` if the merge succeeded without conflicts.
        - ``metrics`` is a :class:`ConflictMetrics` instance, or ``None``
          on checkout failure.
        - ``regions`` is a list of region dicts (empty on a clean merge).
        - ``conflict_files`` is a list of conflicting file paths.
        - ``detail`` is a short diagnostic string.
    """
    run(["git", "reset", "--hard"], cwd=repo_path)
    run(["git", "clean", "-fd"], cwd=repo_path)

    rc, _, err = run(["git", "checkout", "-f", base_oid], cwd=repo_path)
    if rc != 0:
        return False, None, [], [], f"base_checkout_failed: {err.strip()[:200]}"

    run(["git", "checkout", "-B", "__agentconflict_tmp__"], cwd=repo_path)

    rc, _, err = run(["git", "merge", "--no-commit", "--no-ff", head_oid], cwd=repo_path)
    if rc == 0:
        run(["git", "merge", "--abort"], cwd=repo_path)
        return True, ConflictMetrics(has_text_conflict=False), [], [], "merge_clean"

    conflict_files = list_conflicting_files(repo_path)
    regions, metrics = compute_conflict_details(repo_path, conflict_files)

    run(["git", "merge", "--abort"], cwd=repo_path)
    return False, metrics, regions, conflict_files, f"merge_failed: {err.strip()[:200]}"