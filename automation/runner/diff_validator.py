from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path

from automation.runner.policies import matches_any


@dataclass(frozen=True)
class DiffValidation:
    ok: bool
    changed_files: list[str]
    reason: str = ""


def _clean_diff_path(path: str) -> str:
    path = path.strip()
    if path == "/dev/null":
        return path
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        path = _decode_git_quoted_path(path[1:-1])
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _decode_git_quoted_path(path: str) -> str:
    decoded = bytearray()
    i = 0
    while i < len(path):
        char = path[i]
        if char == "\\" and i + 1 < len(path):
            next_char = path[i + 1]
            octal = path[i + 1 : i + 4]
            if len(octal) == 3 and all("0" <= digit <= "7" for digit in octal):
                decoded.append(int(octal, 8))
                i += 4
                continue
            escapes = {
                "\\": ord("\\"),
                '"': ord('"'),
                "n": ord("\n"),
                "t": ord("\t"),
                "r": ord("\r"),
                "b": ord("\b"),
                "f": ord("\f"),
                "a": ord("\a"),
                "v": ord("\v"),
            }
            if next_char in escapes:
                decoded.append(escapes[next_char])
                i += 2
                continue
        decoded.extend(char.encode("utf-8"))
        i += 1
    return decoded.decode("utf-8")


def changed_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = _clean_diff_path(line[4:])
            if path != "/dev/null" and path not in files:
                files.append(path)
    return files


def validate_patch(
    patch: str,
    *,
    allowed_paths: list[str],
    forbidden_paths: list[str],
    max_patch_bytes: int,
    max_changed_files: int,
) -> DiffValidation:
    if len(patch.encode("utf-8")) > max_patch_bytes:
        return DiffValidation(False, [], "patch exceeds size limit")
    changed_files = changed_files_from_patch(patch)
    if not changed_files:
        return DiffValidation(False, [], "patch does not change any files")
    if len(changed_files) > max_changed_files:
        return DiffValidation(False, changed_files, "patch changes too many files")
    for path in changed_files:
        if Path(path).is_absolute() or ".." in Path(path).parts:
            return DiffValidation(False, changed_files, f"unsafe patch path: {path}")
        if matches_any(path, forbidden_paths):
            return DiffValidation(False, changed_files, f"patch touches forbidden path: {path}")
        if not any(fnmatch.fnmatch(path, pattern) for pattern in allowed_paths):
            return DiffValidation(False, changed_files, f"patch touches outside allowed paths: {path}")
    return DiffValidation(True, changed_files)


def apply_unified_patch(root: Path, patch: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), "apply", "--whitespace=nowarn", "--binary", "-"],
        input=patch,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return
    if "diff --git" in patch:
        reason = result.stderr.strip() or result.stdout.strip() or "git apply failed"
        raise ValueError(reason)
    _apply_simple_unified_patch(root, patch)


def _apply_simple_unified_patch(root: Path, patch: str) -> None:
    current_file: Path | None = None
    old_lines: list[str] = []
    new_lines: list[str] = []

    def flush() -> None:
        nonlocal current_file, old_lines, new_lines
        if current_file is None:
            return
        if not current_file.exists():
            if old_lines:
                raise ValueError(f"patch context does not match: {current_file.relative_to(root)}")
            current_file.parent.mkdir(parents=True, exist_ok=True)
            current_file.write_text("".join(new_lines), encoding="utf-8")
        else:
            original = current_file.read_text(encoding="utf-8").splitlines(keepends=True)
            if original != old_lines:
                raise ValueError(f"patch context does not match: {current_file.relative_to(root)}")
            current_file.write_text("".join(new_lines), encoding="utf-8")
        current_file = None
        old_lines = []
        new_lines = []

    for line in patch.splitlines(keepends=True):
        if line.startswith("--- "):
            flush()
            current_file = None
            old_lines = []
            new_lines = []
            continue
        if line.startswith("+++ "):
            path = _clean_diff_path(line[4:].strip())
            current_file = root / path
            continue
        if line.startswith("@@"):
            continue
        if current_file is None:
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        elif line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
    flush()
