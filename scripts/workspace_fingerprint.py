#!/usr/bin/env python3
"""Bounded-memory Git dirty-state fingerprints, including untracked files."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any, Iterable

CHUNK_SIZE = 1024 * 1024
GIT_TIMEOUT_SECONDS = 60


def _git_bytes(workspace: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), *args],
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _status_entries(raw: bytes) -> list[tuple[bytes, bytes]]:
    """Return (XY, path) from porcelain v1 -z; rename source entries are skipped."""
    parts = raw.split(b"\0")
    entries: list[tuple[bytes, bytes]] = []
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item or len(item) < 4:
            continue
        status, path = item[:2], item[3:]
        entries.append((status, path))
        if b"R" in status or b"C" in status:
            index += 1
    return entries


def _hash_git_output(workspace: Path, digest: Any, *args: str) -> bool:
    """Stream Git output into a digest so large tracked binary diffs stay memory-bounded."""
    try:
        process = subprocess.Popen(
            ["git", "-C", str(workspace), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    assert process.stdout is not None
    with process.stdout:
        for chunk in iter(lambda: process.stdout.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return process.wait() == 0


def dirty_hash(workspace: Path, excluded_roots: Iterable[Path] = ()) -> tuple[bool, str | None]:
    """Hash status, tracked diffs, and untracked content without loading files into memory."""
    workspace = workspace.resolve()
    excluded = [root.resolve() for root in excluded_roots]
    excluded = [root for root in excluded if _inside(root, workspace)]
    raw_status = _git_bytes(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if raw_status is None:
        return False, None

    filtered: list[tuple[bytes, bytes, Path]] = []
    for status, raw_path in _status_entries(raw_status):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        candidate = (workspace / relative).resolve()
        if not _inside(candidate, workspace):
            continue
        if any(_inside(candidate, root) for root in excluded):
            continue
        filtered.append((status, raw_path, candidate))
    if not filtered:
        return False, None

    diff_args = ["diff", "--binary", "HEAD", "--", "."]
    for root in excluded:
        relative = root.relative_to(workspace).as_posix()
        diff_args.extend([f":(exclude){relative}", f":(exclude){relative}/**"])
    digest = hashlib.sha256()
    for status, raw_path, _ in filtered:
        digest.update(status + b" " + raw_path + b"\0")
    digest.update(b"DIFF\0")
    if not _hash_git_output(workspace, digest, *diff_args):
        digest.update(b"<git-diff-unavailable>")
    for status, raw_path, candidate in filtered:
        if status != b"??" or not candidate.is_file() or candidate.is_symlink():
            continue
        digest.update(b"UNTRACKED\0" + raw_path + b"\0")
        try:
            with candidate.open("rb") as stream:
                for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
                    digest.update(chunk)
        except OSError:
            digest.update(b"<unreadable>")
    return True, digest.hexdigest()
