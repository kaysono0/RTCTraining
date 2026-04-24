from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.runner.artifact_store import ArtifactStore


def _as_json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_runtime_event(root: Path, task_id: str, event: dict[str, Any]) -> None:
    artifacts = ArtifactStore(root)
    artifacts.ensure()
    path = artifacts.base / "transcripts" / f"{task_id}.jsonl"
    payload = {"at": _utc_now_iso(), **event}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _stream_output_lines(
    *,
    root: Path,
    task_id: str,
    stream_name: str,
    pipe,
    chunks: list[str],
) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            chunks.append(line)
            _append_runtime_event(
                root,
                task_id,
                {
                    "type": f"codex_exec_{stream_name}",
                    "stream": stream_name,
                    "chunk": line,
                    "chunk_bytes": len(line.encode("utf-8")),
                },
            )
    finally:
        pipe.close()


def _looks_like_patch(text: str) -> bool:
    return bool(re.search(r"(?m)^(diff --git |\*\*\* Begin Patch|@@ )", text))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _baseline_summary(task: dict[str, Any]) -> dict[str, Any]:
    baseline = task.get("baseline", {})
    files: list[Any] = []
    patterns: list[Any] = []
    kind = "n/a"
    digest = "n/a"
    if isinstance(baseline, dict):
        kind = str(baseline.get("kind", "n/a"))
        digest = str(baseline.get("digest", "n/a"))
        files = baseline.get("files", []) if isinstance(baseline.get("files", []), list) else []
        patterns = baseline.get("patterns", []) if isinstance(baseline.get("patterns", []), list) else []
    return {
        "kind": kind,
        "digest": digest,
        "file_count": len(files),
        "pattern_count": len(patterns),
    }


def _request_summary(payload: dict[str, Any]) -> dict[str, Any]:
    task = payload.get("task", {})
    plan = payload.get("plan", {})
    failed_checks = payload.get("failed_checks", [])
    summary = {
        "phase": str(payload.get("phase", "develop")),
        "task_id": str(task.get("id", "unknown-task")),
        "title": str(task.get("title", "")),
        "goal": str(task.get("goal", "")),
        "context_files": _string_list(task.get("context_files", [])),
        "allowed_paths": _string_list(task.get("allowed_paths", [])),
        "required_checks": _string_list(task.get("required_checks", [])),
        "baseline": _baseline_summary(task),
    }
    if isinstance(plan, dict) and plan:
        summary["plan_summary"] = str(plan.get("summary", ""))
        summary["plan_files_to_change"] = _string_list(plan.get("files_to_change", []))
    if failed_checks:
        summary["failed_checks_count"] = len(failed_checks)
    if "repair_attempt" in payload:
        summary["repair_attempt"] = int(payload.get("repair_attempt", 0) or 0)
    return summary


def _baseline_lines(task: dict[str, Any]) -> list[str]:
    baseline = _baseline_summary(task)
    context_files = _string_list(task.get("context_files", []))
    allowed_paths = _string_list(task.get("allowed_paths", []))
    required_checks = _string_list(task.get("required_checks", []))
    return [
        "Baseline summary:",
        f"- Kind: {baseline['kind']}",
        f"- Digest: `{baseline['digest']}`",
        f"- Manifest file count: {baseline['file_count']}",
        f"- Pattern count: {baseline['pattern_count']}",
        f"- Context file count: {len(context_files)}",
        f"- Allowed path count: {len(allowed_paths)}",
        f"- Required check count: {len(required_checks)}",
    ]


def build_prompt(payload: dict[str, Any]) -> str:
    phase = str(payload.get("phase", "develop"))
    task = payload.get("task", {})
    plan = payload.get("plan", {})
    failed_checks = payload.get("failed_checks", [])
    task_json = _as_json_text(task)
    plan_json = _as_json_text(plan)
    failed_checks_json = _as_json_text(failed_checks)
    context_files = _string_list(task.get("context_files", []))
    allowed_paths = _string_list(task.get("allowed_paths", []))
    acceptance = _string_list(task.get("acceptance", []))
    required_checks = _string_list(task.get("required_checks", []))
    acceptance_lines = [f"- {item}" for item in acceptance] or ["- n/a"]
    required_check_lines = [f"- {item}" for item in required_checks] or ["- n/a"]
    context_file_lines = [f"- {item}" for item in context_files] or ["- n/a"]
    allowed_path_lines = [f"- {item}" for item in allowed_paths] or ["- n/a"]

    lines = [
        "You are operating inside a temporary git worktree for RTCTraining.",
        "Make the requested repository changes directly in the checkout when the phase calls for code changes.",
        "Do not commit, do not push, and do not print explanations.",
        "When finished, stop. The wrapper will export the resulting git diff.",
        "",
        f"Phase: {phase}",
        f"Task goal: {task.get('goal', '')}",
        *(_baseline_lines(task)),
        "",
        "Context files:",
        *context_file_lines,
        "Allowed paths:",
        *allowed_path_lines,
        "Acceptance criteria:",
        *acceptance_lines,
        "Required checks:",
        *required_check_lines,
        "",
        "Task JSON:",
        "```json",
        task_json,
        "```",
    ]
    if phase == "plan":
        lines.extend(
            [
                "",
                "You are creating a plan only. Do not change files.",
                "Ask for a concise plan object only.",
                "",
                "Plan output:",
                "- summary",
                "- files_to_change",
                "- tests_to_run",
                "- risk_notes",
            ]
        )
    elif phase == "develop":
        lines.extend(
            [
                "",
                "Accepted plan:",
                "```json",
                plan_json,
                "```",
                "",
                "Constraints:",
                "- Only change files required by the task.",
                "- Keep the changes consistent with the acceptance criteria and required checks.",
                "- If tests need to run, use the repo's normal commands.",
                "- If the task requests a new file, create it in one of the allowed paths.",
                "- Leave the working tree dirty; the wrapper will capture the diff.",
            ]
        )
    elif phase == "repair":
        lines.extend(
            [
                "",
                f"Repair attempt: {payload.get('repair_attempt', 0)}",
                "Accepted plan:",
                "```json",
                plan_json,
                "```",
                "",
                "Failed checks JSON:",
                "```json",
                failed_checks_json,
                "```",
                "",
                "Constraints:",
                "- Only change files required by the task.",
                "- Keep the changes consistent with the acceptance criteria and required checks.",
                "- Fix the specific failure described in failed checks.",
                "- If tests need to run, use the repo's normal commands.",
                "- Leave the working tree dirty; the wrapper will capture the diff.",
            ],
        )
    else:
        lines.extend(
            [
                "",
                "Constraints:",
                "- Only change files required by the task.",
                "- Keep the changes consistent with the acceptance criteria and required checks.",
                "- If tests need to run, use the repo's normal commands.",
                "- If the task requests a new file, create it in one of the allowed paths.",
                "- Leave the working tree dirty; the wrapper will capture the diff.",
            ]
        )
    return "\n".join(lines)


def _git_toplevel(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def _link_venv(root: Path, snapshot_root: Path) -> None:
    venv = root / ".venv"
    if not venv.exists():
        return
    link = snapshot_root / ".venv"
    if not link.exists():
        link.symlink_to(venv, target_is_directory=True)


def _prepare_worktree(root: Path, task_id: str) -> Path:
    tempdir = Path(tempfile.mkdtemp(prefix="rtc-codex-"))
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(tempdir)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    _link_venv(root, tempdir)
    subprocess.run(
        ["git", "-C", str(tempdir), "status", "--short"],
        check=False,
        capture_output=True,
        text=True,
    )
    return tempdir


def _cleanup_worktree(root: Path, worktree: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    shutil.rmtree(worktree, ignore_errors=True)


def _cli_binary() -> str:
    return os.environ.get("RTC_AUTOMATION_CODEX_BIN", "claude")


def _cli_backend() -> str:
    bin_name = os.path.basename(_cli_binary())
    return "claude" if bin_name == "claude" else "codex"


def _exec_command() -> list[str]:
    command = _cli_binary()
    backend = _cli_backend()
    args: list[str] = [command]
    if backend == "claude":
        args.extend(["execute", "--print"])
    else:
        args.extend(["exec", "--ephemeral", "--full-auto", "--ignore-user-config", "--skip-git-repo-check"])
    model = os.environ.get("RTC_AUTOMATION_CODEX_MODEL", "").strip()
    if model:
        args.extend(["--model", model])
    if backend != "claude":
        profile = os.environ.get("RTC_AUTOMATION_CODEX_PROFILE", "").strip()
        if profile:
            args.extend(["--profile", profile])
    return args


def _cli_command() -> list[str]:
    command = "source ~/.zshrc && " + shlex.join(_exec_command())
    if _cli_backend() != "claude":
        command += " -"
    return ["zsh", "-lc", command]


def _cli_label() -> str:
    return f"{_cli_backend()} exec"


def _codex_timeout_seconds() -> int:
    value = os.environ.get("RTC_AUTOMATION_CODEX_TIMEOUT_SECONDS", "300").strip()
    try:
        timeout = int(value)
    except ValueError:
        return 300
    return max(timeout, 1)


def run_codex(payload: dict[str, Any], root: Path | None = None) -> str:
    repo_root = _git_toplevel(root or Path.cwd())
    task_id = str(payload.get("task", {}).get("id", "unknown-task"))
    workspace_root_str = payload.get("workspace_root")
    if workspace_root_str:
        worktree = Path(workspace_root_str)
        if not (worktree / ".git").exists():
            raise RuntimeError(f"workspace_root is not a git repository: {worktree}")
        subprocess.run(
            ["git", "-C", str(worktree), "status", "--short"],
            check=False, capture_output=True, text=True,
        )
    else:
        worktree = _prepare_worktree(repo_root, task_id)
    worktree_path = worktree
    try:
        prompt = build_prompt(payload)
        _append_runtime_event(
            repo_root,
            task_id,
            {
                "type": "codex_exec_start",
                "command": _cli_command(),
                "cwd": str(worktree),
                "phase": str(payload.get("phase", "develop")),
                "input_summary": _request_summary(payload),
            },
        )
        try:
            proc = subprocess.Popen(
                _cli_command(),
                cwd=worktree,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            _append_runtime_event(
                repo_root,
                task_id,
                {
                    "type": "codex_exec_error",
                    "command": _cli_command(),
                    "cwd": str(worktree),
                    "error": repr(exc),
                },
            )
            raise

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        stdout_thread = threading.Thread(
            target=_stream_output_lines,
            kwargs={
                "root": repo_root,
                "task_id": task_id,
                "stream_name": "stdout",
                "pipe": proc.stdout,
                "chunks": stdout_chunks,
            },
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_stream_output_lines,
            kwargs={
                "root": repo_root,
                "task_id": task_id,
                "stream_name": "stderr",
                "pipe": proc.stderr,
                "chunks": stderr_chunks,
            },
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        try:
            returncode = proc.wait(timeout=_codex_timeout_seconds())
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            returncode = proc.wait()
            stdout_thread.join()
            stderr_thread.join()
            completed_stdout = "".join(stdout_chunks)
            completed_stderr = "".join(stderr_chunks)
            status = subprocess.run(
                ["git", "-C", worktree_path, "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            changed_files = [
                line[3:].strip()
                for line in status.splitlines()
                if line.strip() and len(line) >= 4
            ]
            _append_runtime_event(
                repo_root,
                task_id,
                {
                    "type": "codex_exec_timeout",
                    "command": _cli_command(),
                    "cwd": str(worktree),
                    "timeout_seconds": _codex_timeout_seconds(),
                    "stdout": completed_stdout,
                    "stderr": completed_stderr,
                    "local_files_changed": bool(changed_files),
                    "changed_files": changed_files,
                    "codex_output_has_patch": _looks_like_patch(completed_stdout + completed_stderr),
                },
            )
            raise RuntimeError(f"{_cli_label()} timed out after {_codex_timeout_seconds()} seconds") from exc
        stdout_thread.join()
        stderr_thread.join()
        completed_stdout = "".join(stdout_chunks)
        completed_stderr = "".join(stderr_chunks)
        result = subprocess.CompletedProcess(
            args=_cli_command(),
            returncode=returncode,
            stdout=completed_stdout,
            stderr=completed_stderr,
        )
        _append_runtime_event(
            repo_root,
            task_id,
            {
                "type": "codex_exec_finish",
                "command": _cli_command(),
                "cwd": str(worktree),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "stdout_bytes": len(result.stdout.encode("utf-8")),
                "stderr_bytes": len(result.stderr.encode("utf-8")),
            },
        )
        cli = _cli_label()
        if result.returncode != 0:
            raise RuntimeError(f"{cli} failed with exit code {result.returncode}: {result.stderr.strip()}")
        subprocess.run(
            ["git", "-C", worktree_path, "add", "-A"],
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "-C", worktree_path, "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "HEAD", "--"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        changed_files = [
            line.strip()
            for line in status.splitlines()
            if line.strip()
        ]
        try:
            diff = subprocess.run(
                ["git", "-C", worktree_path, "diff", "--cached", "--binary", "--no-ext-diff", "HEAD", "--"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except Exception as exc:
            _append_runtime_event(
                repo_root,
                task_id,
                {
                    "type": "codex_diff_error",
                    "cwd": str(worktree),
                    "error": repr(exc),
                },
            )
            raise
        _append_runtime_event(
            repo_root,
            task_id,
                {
                    "type": "codex_diff",
                    "cwd": str(worktree),
                    "diff_bytes": len(diff.encode("utf-8")),
                    "has_changes": bool(diff.strip()),
                    "local_files_changed": bool(changed_files),
                    "changed_files": changed_files,
                    "codex_output_has_patch": _looks_like_patch(result.stdout + result.stderr),
                    "exported_patch": bool(diff.strip()),
                },
            )
        return diff
    finally:
        _cleanup_worktree(repo_root, worktree)


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Bridge RTCTraining model requests to {_cli_label()}")
    parser.add_argument("--root", default=".", help="Repository root, defaults to the current directory")
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    diff = run_codex(payload, Path(args.root))
    sys.stdout.write(diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
