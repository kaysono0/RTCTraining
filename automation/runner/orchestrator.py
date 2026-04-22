from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automation.runner.artifact_store import ArtifactStore, utc_now_iso
from automation.runner.diff_validator import apply_unified_patch, validate_patch
from automation.runner.model_gateway import build_model_gateway
from automation.runner.policies import Policy
from automation.runner.task_loader import Task, TaskLoader
from automation.runner.test_runner import CheckResult, TestRunner
from automation.runner.worktree_manager import WorktreeManager


@dataclass(frozen=True)
class RunResult:
    task_id: str | None
    status: str
    reason: str = ""


def _block_for_approval(task: Task, loader: TaskLoader, artifacts: ArtifactStore, reason: str) -> RunResult:
    artifacts.write_json(
        f"approvals/{task.id}.json",
        {
            "task_id": task.id,
            "reason": reason,
            "created_at": utc_now_iso(),
            "required_user_action": "Review the task contract and move it back to ready after approval.",
        },
    )
    artifacts.write_json(
        f"reports/{task.id}.json",
        {"task_id": task.id, "status": "blocked", "reason": reason, "checks": [], "changed_files": []},
    )
    loader.move(task, "blocked")
    return RunResult(task.id, "blocked", f"approval required: {reason}")


def _fail(task: Task, loader: TaskLoader, artifacts: ArtifactStore, reason: str, changed_files: list[str] | None = None) -> RunResult:
    artifacts.write_json(
        f"reports/{task.id}.json",
        {
            "task_id": task.id,
            "status": "failed",
            "reason": reason,
            "checks": [],
            "changed_files": changed_files or [],
        },
    )
    loader.move(task, "failed")
    return RunResult(task.id, "failed", reason)


def _write_markdown_report(
    artifacts: ArtifactStore,
    task: Task,
    status: str,
    changed_files: list[str],
    checks: list[CheckResult],
    reason: str = "",
) -> None:
    lines = [
        f"# Automation Task Report: {task.id}",
        "",
        f"- Status: {status}",
        f"- Goal: {task.data['goal']}",
        f"- Reason: {reason or 'n/a'}",
        "",
        "## Changed Files",
        *(f"- {path}" for path in changed_files),
        "",
        "## Checks",
        *(f"- `{check.command}`: {check.status} ({check.exit_code})" for check in checks),
        "",
    ]
    artifacts.write_text(f"reports/{task.id}.md", "\n".join(lines))


def _workspace_for_task(root: Path, task: Task) -> tuple[Path, str, str | None]:
    mode = str(task.data.get("mode", "patch-only"))
    if mode == "patch-only":
        return root, ".", None
    if mode == "worktree":
        worktree = WorktreeManager(root).create(task.id)
        return worktree.path, worktree.relative_path, worktree.branch
    raise RuntimeError(f"unsupported task mode: {mode}")


def _load_runtime(root: Path) -> dict[str, Any]:
    path = root / "automation/config/runtime.json"
    if not path.exists():
        return {"model_backend": "stub"}
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_patch_for_task(patch: str, task: Task, policy: Policy):
    return validate_patch(
        patch,
        allowed_paths=list(task.data["allowed_paths"]),
        forbidden_paths=policy.forbidden_patterns(task.data),
        max_patch_bytes=policy.max_patch_bytes,
        max_changed_files=policy.max_changed_files,
    )


def _run_required_checks(
    workspace_root: Path,
    root: Path,
    policy: Policy,
    artifacts: ArtifactStore,
    task_id: str,
    commands: list[str],
) -> list[CheckResult]:
    return TestRunner(workspace_root, policy, artifacts, command_root=root).run_checks(task_id, commands)


def _failed_check_payload(checks: list[CheckResult]) -> list[dict[str, Any]]:
    return [check.__dict__ for check in checks if check.status != "passed"]


def run_once(root: str | Path = ".") -> RunResult:
    root = Path(root)
    artifacts = ArtifactStore(root)
    artifacts.ensure()
    loader = TaskLoader(root)
    loader.ensure()
    task = loader.next_ready()
    if task is None:
        return RunResult(None, "idle", "no ready tasks")

    policy = Policy(root)
    decision = policy.evaluate_task(task.data)
    if decision.requires_approval:
        return _block_for_approval(task, loader, artifacts, decision.reason)
    if not decision.allowed:
        return _fail(task, loader, artifacts, decision.reason)

    task_path = loader.move(task, "running")
    task = Task(path=task_path, data=task.data)
    try:
        workspace_root, workspace_path, worktree_branch = _workspace_for_task(root, task)
    except Exception as exc:
        return _fail(task, loader, artifacts, str(exc))

    try:
        model = build_model_gateway(root, artifacts, _load_runtime(root), policy.command_timeout_seconds)
        plan = model.plan(task.data)
        artifacts.write_json(f"plans/{task.id}.json", plan)
        patch = model.develop(task.data, plan)
    except Exception as exc:
        return _fail(task, loader, artifacts, str(exc))
    artifacts.write_text(f"patches/{task.id}.patch", patch)

    validation = _validate_patch_for_task(patch, task, policy)
    if not validation.ok:
        return _fail(task, loader, artifacts, validation.reason, validation.changed_files)

    try:
        apply_unified_patch(workspace_root, patch)
    except Exception as exc:
        return _fail(task, loader, artifacts, str(exc), validation.changed_files)

    checks = _run_required_checks(workspace_root, root, policy, artifacts, task.id, list(task.data["required_checks"]))
    repair_attempts = 0
    max_repair_attempts = int(task.data.get("max_repair_attempts", policy.data.get("default_max_repair_attempts", 0)))
    while any(check.status != "passed" for check in checks) and repair_attempts < max_repair_attempts:
        repair_attempts += 1
        try:
            repair_patch = model.repair(task.data, plan, _failed_check_payload(checks), repair_attempts)
        except Exception as exc:
            return _fail(task, loader, artifacts, str(exc), validation.changed_files)
        artifacts.write_text(f"patches/{task.id}.repair-{repair_attempts}.patch", repair_patch)
        repair_validation = _validate_patch_for_task(repair_patch, task, policy)
        if not repair_validation.ok:
            return _fail(task, loader, artifacts, repair_validation.reason, repair_validation.changed_files)
        try:
            apply_unified_patch(workspace_root, repair_patch)
        except Exception as exc:
            return _fail(task, loader, artifacts, str(exc), repair_validation.changed_files)
        changed_files = list(dict.fromkeys(validation.changed_files + repair_validation.changed_files))
        validation = type(validation)(True, changed_files)
        checks = _run_required_checks(
            workspace_root,
            root,
            policy,
            artifacts,
            task.id,
            list(task.data["required_checks"]),
        )
    status = "done" if all(check.status == "passed" for check in checks) else "failed"
    report = {
        "task_id": task.id,
        "status": status,
        "mode": str(task.data.get("mode", "patch-only")),
        "workspace_path": workspace_path,
        "worktree_branch": worktree_branch,
        "repair_attempts": repair_attempts,
        "reason": "" if status == "done" else "required checks failed",
        "changed_files": validation.changed_files,
        "checks": [check.__dict__ for check in checks],
        "artifacts": {
            "plan": f"automation/artifacts/plans/{task.id}.json",
            "patch": f"automation/artifacts/patches/{task.id}.patch",
            "report": f"automation/artifacts/reports/{task.id}.md",
        },
    }
    artifacts.write_json(f"reports/{task.id}.json", report)
    _write_markdown_report(artifacts, task, status, validation.changed_files, checks, report["reason"])
    loader.move(task, status)
    return RunResult(task.id, status, report["reason"])


def run_continuous(
    root: str | Path = ".",
    *,
    max_tasks: int = 1,
    poll_interval_seconds: float = 30.0,
) -> list[RunResult]:
    results: list[RunResult] = []
    while len(results) < max_tasks:
        result = run_once(root)
        if result.status == "idle":
            break
        results.append(result)
        if poll_interval_seconds:
            time.sleep(poll_interval_seconds)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="RTCTraining autonomous automation runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-once", help="Run the next ready task once")
    continuous = subparsers.add_parser("run-continuous", help="Run ready tasks until the limit or queue is empty")
    continuous.add_argument("--max-tasks", type=int, default=1)
    continuous.add_argument("--poll-interval-seconds", type=float, default=30.0)

    args = parser.parse_args()
    if args.command == "run-once":
        print(json.dumps(run_once().__dict__, ensure_ascii=False))
        return 0
    if args.command == "run-continuous":
        results = run_continuous(max_tasks=args.max_tasks, poll_interval_seconds=args.poll_interval_seconds)
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
