from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BaselineCheckResult:
    ok: bool
    reason: str = ""
    changed_paths: list[str] | None = None


def build_task_baseline(root: Path, context_files: list[str], allowed_paths: list[str]) -> dict[str, Any]:
    manifest = _collect_manifest(root, list(context_files) + list(allowed_paths))
    digest = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "kind": "file-manifest",
        "digest": digest,
        "patterns": list(context_files) + list(allowed_paths),
        "files": manifest,
    }


def validate_task_baseline(root: Path, baseline: dict[str, Any]) -> BaselineCheckResult:
    if not isinstance(baseline, dict):
        return BaselineCheckResult(False, "task baseline must be an object")
    if baseline.get("kind") != "file-manifest":
        return BaselineCheckResult(False, "task baseline has unsupported kind")
    files = baseline.get("files")
    patterns = baseline.get("patterns")
    digest = baseline.get("digest")
    if not isinstance(files, list) or not isinstance(digest, str):
        return BaselineCheckResult(False, "task baseline is missing manifest data")

    if isinstance(patterns, list) and patterns:
        current_files = _collect_manifest(root, [str(value) for value in patterns])
    else:
        current_files = _collect_manifest_from_entries(root, files)
    current_digest = hashlib.sha256(
        json.dumps(current_files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if current_digest == digest:
        return BaselineCheckResult(True, changed_paths=[])

    changed_paths = _changed_paths(files, current_files)
    reason = "task baseline mismatch"
    if changed_paths:
        reason = f"task baseline mismatch: {', '.join(changed_paths[:5])}"
    return BaselineCheckResult(False, reason, changed_paths)


def _collect_manifest(root: Path, patterns: list[str]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for pattern in patterns:
        matches = sorted(path for path in root.glob(pattern) if path.is_file())
        if matches:
            for path in matches:
                rel = path.relative_to(root).as_posix()
                entries[rel] = _file_entry(path, rel)
            continue
        if _looks_like_glob(pattern):
            continue
        rel = Path(pattern).as_posix()
        entries.setdefault(
            rel,
            {
                "path": rel,
                "state": "missing",
                "sha256": None,
                "size": None,
            },
        )
    return [entries[key] for key in sorted(entries)]


def _collect_manifest_from_entries(root: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for entry in entries:
        rel = str(entry["path"])
        path = root / rel
        if path.is_file():
            current[rel] = _file_entry(path, rel)
        else:
            current[rel] = {
                "path": rel,
                "state": "missing",
                "sha256": None,
                "size": None,
            }
    return [current[key] for key in sorted(current)]


def _changed_paths(expected: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[str]:
    current_map = {str(entry["path"]): entry for entry in current}
    changed: list[str] = []
    for entry in expected:
        rel = str(entry["path"])
        other = current_map.get(rel)
        if other != entry:
            changed.append(rel)
    return changed


def _file_entry(path: Path, rel: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": rel,
        "state": "present",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def _looks_like_glob(pattern: str) -> bool:
    return any(token in pattern for token in ("*", "?", "[", "]", "{", "}"))
