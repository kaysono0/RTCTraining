from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

from automation.runner.artifact_store import ArtifactStore, utc_now_iso
from automation.runner.diff_validator import apply_unified_patch, validate_patch
from automation.runner.model_gateway import StubModelGateway
from automation.runner.policies import Policy
from automation.runner.task_loader import Task, TaskLoader
from automation.runner.test_runner import CheckResult, TestRunner


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

    model = StubModelGateway(artifacts)
    plan = model.plan(task.data)
    artifacts.write_json(f"plans/{task.id}.json", plan)
    patch = model.develop(task.data, plan)
    artifacts.write_text(f"patches/{task.id}.patch", patch)

    validation = validate_patch(
        patch,
        allowed_paths=list(task.data["allowed_paths"]),
        forbidden_paths=policy.forbidden_patterns(task.data),
        max_patch_bytes=policy.max_patch_bytes,
        max_changed_files=policy.max_changed_files,
    )
    if not validation.ok:
        return _fail(task, loader, artifacts, validation.reason, validation.changed_files)

    try:
        apply_unified_patch(root, patch)
    except Exception as exc:
        return _fail(task, loader, artifacts, str(exc), validation.changed_files)

    checks = TestRunner(root, policy, artifacts).run_checks(task.id, list(task.data["required_checks"]))
    status = "done" if all(check.status == "passed" for check in checks) else "failed"
    report = {
        "task_id": task.id,
        "status": status,
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
