from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any
from pathlib import Path

from automation.runner.artifact_store import ArtifactStore


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _baseline_summary(task: dict[str, Any]) -> dict[str, Any]:
    baseline = task.get("baseline", {})
    kind = "n/a"
    digest = "n/a"
    files: list[Any] = []
    patterns: list[Any] = []
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


def _request_summary(task: dict[str, Any], phase: str, plan: dict[str, Any] | None = None, failed_checks: list[dict[str, Any]] | None = None, attempt: int | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "phase": phase,
        "task_id": str(task.get("id", "unknown-task")),
        "title": str(task.get("title", "")),
        "goal": str(task.get("goal", "")),
        "context_files": _string_list(task.get("context_files", [])),
        "allowed_paths": _string_list(task.get("allowed_paths", [])),
        "required_checks": _string_list(task.get("required_checks", [])),
        "baseline": _baseline_summary(task),
    }
    if plan:
        summary["plan_summary"] = str(plan.get("summary", ""))
        summary["plan_files_to_change"] = _string_list(plan.get("files_to_change", []))
    if failed_checks:
        summary["failed_checks_count"] = len(failed_checks)
    if attempt is not None:
        summary["repair_attempt"] = attempt
    return summary


class StubModelGateway:
    """Deterministic model gateway used by the first local harness and tests."""

    def __init__(self, artifacts: ArtifactStore):
        self.artifacts = artifacts

    def plan(self, task: dict[str, Any]) -> dict[str, Any]:
        plan = {
            "summary": task["goal"],
            "files_to_change": task["allowed_paths"],
            "tests_to_run": task["required_checks"],
            "risk_notes": [f"risk_level={task['risk_level']}"],
        }
        self.artifacts.append_transcript(
            str(task["id"]),
            {"type": "plan", "content": plan, "input_summary": _request_summary(task, "plan", plan)},
        )
        return plan

    def develop(self, task: dict[str, Any], plan: dict[str, Any]) -> str:
        patch = str(task.get("stub_patch", ""))
        self.artifacts.append_transcript(
            str(task["id"]),
            {"type": "develop", "plan_summary": plan["summary"], "patch_bytes": len(patch.encode("utf-8"))},
        )
        return patch

    def repair(
        self,
        task: dict[str, Any],
        plan: dict[str, Any],
        failed_checks: list[dict[str, Any]],
        attempt: int,
    ) -> str:
        patches = task.get("stub_repair_patches", [])
        patch = ""
        if isinstance(patches, list) and attempt - 1 < len(patches):
            patch = str(patches[attempt - 1])
        self.artifacts.append_transcript(
            str(task["id"]),
            {
                "type": "repair",
                "attempt": attempt,
                "failed_checks": failed_checks,
                "patch_bytes": len(patch.encode("utf-8")),
            },
        )
        return patch


class CommandModelGateway:
    """Model gateway that delegates patch generation to a configured command.

    The command receives a JSON request on stdin and must write a unified diff
    to stdout. This keeps provider-specific model calls outside the runner.
    """

    def __init__(
        self,
        root: Path,
        command: str,
        *,
        artifacts: ArtifactStore | None = None,
        timeout_seconds: int = 300,
    ):
        self.root = root
        self.command = command
        self.artifacts = artifacts or ArtifactStore(root)
        self.timeout_seconds = timeout_seconds

    def plan(self, task: dict[str, Any]) -> dict[str, Any]:
        plan = {
            "summary": task["goal"],
            "files_to_change": task["allowed_paths"],
            "tests_to_run": task["required_checks"],
            "risk_notes": [f"risk_level={task['risk_level']}"],
        }
        self.artifacts.append_transcript(
            str(task["id"]),
            {"type": "plan", "content": plan, "input_summary": _request_summary(task, "plan", plan)},
        )
        return plan

    def develop(self, task: dict[str, Any], plan: dict[str, Any]) -> str:
        patch = self._run({"phase": "develop", "task": task, "plan": plan})
        self.artifacts.append_transcript(
            str(task["id"]),
            {"type": "develop", "backend": "command", "patch_bytes": len(patch.encode("utf-8"))},
        )
        return patch

    def repair(
        self,
        task: dict[str, Any],
        plan: dict[str, Any],
        failed_checks: list[dict[str, Any]],
        attempt: int,
    ) -> str:
        patch = self._run(
            {
                "phase": "repair",
                "attempt": attempt,
                "task": task,
                "plan": plan,
                "failed_checks": failed_checks,
            }
        )
        self.artifacts.append_transcript(
            str(task["id"]),
            {
                "type": "repair",
                "backend": "command",
                "attempt": attempt,
                "patch_bytes": len(patch.encode("utf-8")),
            },
        )
        return patch

    def _run(self, payload: dict[str, Any]) -> str:
        result = subprocess.run(
            shlex.split(self.command),
            cwd=self.root,
            input=json.dumps(payload, ensure_ascii=False),
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(f"model command failed with exit code {result.returncode}: {result.stderr.strip()}")
        return result.stdout


def build_model_gateway(root: Path, artifacts: ArtifactStore, runtime: dict[str, Any], timeout_seconds: int):
    backend = str(runtime.get("model_backend", "stub"))
    if backend == "stub":
        return StubModelGateway(artifacts)
    if backend == "command":
        command = str(runtime.get("model_command", "")).strip()
        if not command:
            raise RuntimeError("runtime model_backend=command requires model_command")
        return CommandModelGateway(root, command, artifacts=artifacts, timeout_seconds=timeout_seconds)
    raise RuntimeError(f"unsupported model backend: {backend}")
