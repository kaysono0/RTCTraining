from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automation.runner.artifact_store import ArtifactStore, utc_now_iso
from automation.runner.diff_validator import apply_unified_patch, validate_patch
from automation.runner.model_gateway import build_model_gateway
from automation.runner.policies import Policy
from automation.runner.task_supply import TaskSupplyManager
from automation.runner.task_baseline import validate_task_baseline
from automation.runner.task_loader import Task, TaskLoader
from automation.runner.test_runner import CheckResult, TestRunner
from automation.runner.worktree_manager import WorktreeManager


@dataclass(frozen=True)
class RunResult:
    task_id: str | None
    status: str
    reason: str = ""


def _block_for_approval(
    task: Task,
    loader: TaskLoader,
    artifacts: ArtifactStore,
    reason: str,
    changed_files: list[str] | None = None,
) -> RunResult:
    artifacts.write_json(
        f"approvals/{task.id}.json",
        {
            "task_id": task.id,
            "reason": reason,
            "created_at": utc_now_iso(),
            "required_user_action": "Review the task contract and move it back to ready after approval.",
            "changed_files": changed_files or [],
        },
    )
    artifacts.write_json(
        f"reports/{task.id}.json",
        {
            "task_id": task.id,
            "status": "blocked",
            "reason": reason,
            "checks": [],
            "changed_files": changed_files or [],
        },
    )
    _write_markdown_report(artifacts, task, "blocked", changed_files or [], [], reason)
    loader.move(task, "blocked")
    return RunResult(task.id, "blocked", f"approval required: {reason}")


def _fail(
    task: Task,
    loader: TaskLoader,
    artifacts: ArtifactStore,
    reason: str,
    changed_files: list[str] | None = None,
    *,
    failure_stage: str = "",
    repair_attempts: int = 0,
) -> RunResult:
    artifacts.write_json(
        f"reports/{task.id}.json",
        {
            "task_id": task.id,
            "status": "failed",
            "reason": reason,
            "failure_stage": failure_stage,
            "repair_attempts": repair_attempts,
            "checks": [],
            "changed_files": changed_files or [],
        },
    )
    _write_markdown_report(
        artifacts,
        task,
        "failed",
        changed_files or [],
        [],
        reason,
        failure_stage=failure_stage,
        repair_attempts=repair_attempts,
    )
    loader.move(task, "failed")
    return RunResult(task.id, "failed", reason)


def _block_for_baseline(task: Task, loader: TaskLoader, artifacts: ArtifactStore, reason: str, changed_files: list[str] | None = None) -> RunResult:
    artifacts.write_json(
        f"reports/{task.id}.json",
        {
            "task_id": task.id,
            "status": "blocked",
            "reason": reason,
            "checks": [],
            "changed_files": changed_files or [],
        },
    )
    _write_markdown_report(artifacts, task, "blocked", changed_files or [], [], reason)
    artifacts.write_json(
        f"approvals/{task.id}.json",
        {
            "task_id": task.id,
            "reason": reason,
            "created_at": utc_now_iso(),
            "required_user_action": "Regenerate the task from the current baseline before retrying.",
        },
    )
    loader.move(task, "blocked")
    return RunResult(task.id, "blocked", f"baseline mismatch: {reason}")


def _write_markdown_report(
    artifacts: ArtifactStore,
    task: Task,
    status: str,
    changed_files: list[str],
    checks: list[CheckResult],
    reason: str = "",
    *,
    failure_stage: str = "",
    repair_attempts: int = 0,
) -> None:
    baseline = task.data.get("baseline")
    baseline_kind = "n/a"
    baseline_digest = "n/a"
    baseline_file_count = 0
    if isinstance(baseline, dict):
        baseline_kind = str(baseline.get("kind", "n/a"))
        baseline_digest = str(baseline.get("digest", "n/a"))
        files = baseline.get("files", [])
        if isinstance(files, list):
            baseline_file_count = len(files)
    context_files = [str(value) for value in task.data.get("context_files", [])]
    required_checks = [str(value) for value in task.data.get("required_checks", [])]
    lines = [
        f"# Automation Task Report: {task.id}",
        "",
        f"- Status: {status}",
        f"- Goal: {task.data['goal']}",
        f"- Reason: {reason or 'n/a'}",
        "",
        "## Baseline Summary",
        f"- Kind: {baseline_kind}",
        f"- Digest: `{baseline_digest}`",
        f"- Manifest file count: {baseline_file_count}",
        f"- Context file count: {len(context_files)}",
        f"- Required check count: {len(required_checks)}",
        "",
        "## Context Files",
        *_markdown_list(context_files),
        "",
        "## Required Checks",
        *_markdown_list(required_checks),
        "",
        "## Changed Files",
        *_markdown_list(changed_files, wrap_backticks=True),
        "",
        "## Checks",
        *(f"- `{check.command}`: {check.status} ({check.exit_code})" for check in checks),
        "",
    ]
    if status == "failed":
        lines.extend(
            [
                "## Failure Summary",
                f"- Stage: {failure_stage or 'n/a'}",
                f"- Repair Attempts: {repair_attempts}",
                f"- Reason: {reason or 'n/a'}",
                "",
            ]
        )
    artifacts.write_text(f"reports/{task.id}.md", "\n".join(lines))


def _markdown_list(items: list[str], *, wrap_backticks: bool = False) -> list[str]:
    if not items:
        return ["- n/a"]
    if wrap_backticks:
        return [f"- `{item}`" for item in items]
    return [f"- {item}" for item in items]


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


def _patch_failure_payload(reason: str) -> list[dict[str, Any]]:
    return [
        {
            "command": "apply patch",
            "status": "failed",
            "exit_code": 1,
            "duration_ms": 0,
            "log_path": "",
            "reason": reason,
        }
    ]


def _is_patch_context_mismatch(reason: str) -> bool:
    return "patch context does not match" in reason


def _is_major_patch_reason(reason: str) -> bool:
    return "size limit" in reason or "too many files" in reason


def _workspace_has_changes(workspace_root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(workspace_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _integrate_task(
    _root: Path,
    task: Task,
    workspace_root: Path,
    report: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Auto-commit, push, and create PR for a completed low-risk task.

    Controlled by runtime.json keys:
      auto_integrate (bool) — master switch
      auto_integrate_risk_levels (list[str]) — default ["low"]
      auto_integrate_branch_prefix (str) — default "auto/task-"
      auto_integrate_remote (str) — default "origin"

    Returns dict with branch / pr_url on success, or error / skipped.
    """
    if not runtime.get("auto_integrate", False):
        return {}
    allowed_risks = runtime.get("auto_integrate_risk_levels", ["low"])
    if task.risk_level not in allowed_risks:
        return {"skipped": f"risk level {task.risk_level} not in {allowed_risks}"}

    remote = runtime.get("auto_integrate_remote", "origin")
    branch_prefix = runtime.get("auto_integrate_branch_prefix", "auto/task-")
    branch = f"{branch_prefix}{task.id}"

    title = task.data.get("title", task.id)
    try:
        exists = (
            subprocess.run(
                ["git", "-C", str(workspace_root), "rev-parse", "--verify", branch],
                check=False,
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )
        if exists:
            return {"skipped": f"branch already exists: {branch}"}

        if not _workspace_has_changes(workspace_root):
            return {"skipped": "no changes to integrate"}

        subprocess.run(
            ["git", "-C", str(workspace_root), "checkout", "-b", branch],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(workspace_root), "add", "-A"],
            check=True,
            capture_output=True,
            text=True,
        )

        commit_msg = f"auto: {title}\n\n{task.data.get('goal', '')}"
        subprocess.run(
            ["git", "-C", str(workspace_root), "commit", "-m", commit_msg],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", remote, branch],
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )

        changed = report.get("changed_files", [])
        checks = report.get("checks", [])
        pr_body_lines = [
            f"## Summary\n{task.data.get('goal', '')}\n",
            "## Changes",
            *(f"- `{f}`" for f in changed),
            "",
            "## Checks",
            *(f"- `{c['command']}`: {c['status']}" for c in checks),
            "",
            "_Generated by RTCTraining Automation Runner_",
        ]
        pr_url = subprocess.run(
            [
                "gh", "pr", "create",
                "--title", f"auto: {title}",
                "--body", "\n".join(pr_body_lines),
            ],
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return {"branch": branch, "pr_url": pr_url}
    except Exception as exc:
        return {"error": str(exc)}


def run_once(root: str | Path = ".") -> RunResult:
    root = Path(root)
    artifacts = ArtifactStore(root)
    artifacts.ensure()
    loader = TaskLoader(root)
    loader.ensure()
    TaskSupplyManager(root).replenish()
    task = loader.next_ready()
    if task is None:
        return RunResult(None, "idle", "no ready tasks")

    policy = Policy(root)
    decision = policy.evaluate_task(task.data)
    if decision.requires_approval:
        return _block_for_approval(task, loader, artifacts, decision.reason)
    if not decision.allowed:
        return _fail(task, loader, artifacts, decision.reason)

    baseline = task.data.get("baseline")
    if baseline is None:
        return _block_for_baseline(task, loader, artifacts, "task baseline is missing")
    baseline_check = validate_task_baseline(root, baseline)
    if not baseline_check.ok:
        return _block_for_baseline(task, loader, artifacts, baseline_check.reason, baseline_check.changed_paths or [])

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
        patch = model.develop(task.data, plan, workspace_root=str(workspace_root))
    except Exception as exc:
        return _fail(task, loader, artifacts, str(exc), failure_stage="model")
    artifacts.write_text(f"patches/{task.id}.patch", patch)

    validation = _validate_patch_for_task(patch, task, policy)
    if not validation.ok:
        if _is_major_patch_reason(validation.reason):
            return _block_for_approval(task, loader, artifacts, validation.reason, validation.changed_files)
        return _fail(task, loader, artifacts, validation.reason, validation.changed_files, failure_stage="patch_validation")

    repair_attempts = 0
    max_repair_attempts = int(task.data.get("max_repair_attempts", policy.data.get("default_max_repair_attempts", 0)))
    try:
        apply_unified_patch(workspace_root, patch)
    except Exception as exc:
        patch_failure_reason = str(exc)
        if not _is_patch_context_mismatch(patch_failure_reason):
            return _fail(
                task,
                loader,
                artifacts,
                patch_failure_reason,
                validation.changed_files,
                failure_stage="patch_apply",
            )
        repair_checks = _patch_failure_payload(patch_failure_reason)
        while repair_attempts < max_repair_attempts:
            repair_attempts += 1
            try:
                repair_patch = model.repair(task.data, plan, repair_checks, repair_attempts, workspace_root=str(workspace_root))
            except Exception as repair_exc:
                return _fail(
                    task,
                    loader,
                    artifacts,
                    str(repair_exc),
                    validation.changed_files,
                    failure_stage="repair_model",
                    repair_attempts=repair_attempts,
                )
            artifacts.write_text(f"patches/{task.id}.repair-{repair_attempts}.patch", repair_patch)
            repair_validation = _validate_patch_for_task(repair_patch, task, policy)
            if not repair_validation.ok:
                repair_failure_reason = repair_validation.reason
                if _is_major_patch_reason(repair_failure_reason):
                    return _block_for_approval(task, loader, artifacts, repair_failure_reason, repair_validation.changed_files)
                if _is_patch_context_mismatch(repair_failure_reason) and repair_attempts < max_repair_attempts:
                    repair_checks = _patch_failure_payload(repair_failure_reason)
                    continue
                return _fail(
                    task,
                    loader,
                    artifacts,
                    repair_failure_reason,
                    repair_validation.changed_files,
                    failure_stage="repair_patch_validation",
                    repair_attempts=repair_attempts,
                )
            try:
                apply_unified_patch(workspace_root, repair_patch)
            except Exception as repair_exc:
                repair_failure_reason = str(repair_exc)
                if _is_patch_context_mismatch(repair_failure_reason) and repair_attempts < max_repair_attempts:
                    repair_checks = _patch_failure_payload(repair_failure_reason)
                    continue
                return _fail(
                    task,
                    loader,
                    artifacts,
                    repair_failure_reason,
                    repair_validation.changed_files,
                    failure_stage="repair_patch_apply",
                    repair_attempts=repair_attempts,
                )
            validation = type(repair_validation)(True, repair_validation.changed_files)
            break
        else:
            return _fail(
                task,
                loader,
                artifacts,
                patch_failure_reason,
                validation.changed_files,
                failure_stage="patch_apply",
                repair_attempts=repair_attempts,
            )

    checks = _run_required_checks(workspace_root, root, policy, artifacts, task.id, list(task.data["required_checks"]))
    while any(check.status != "passed" for check in checks) and repair_attempts < max_repair_attempts:
        repair_attempts += 1
        try:
            repair_patch = model.repair(task.data, plan, _failed_check_payload(checks), repair_attempts)
        except Exception as exc:
            return _fail(
                task,
                loader,
                artifacts,
                str(exc),
                validation.changed_files,
                failure_stage="repair_model",
                repair_attempts=repair_attempts,
            )
        artifacts.write_text(f"patches/{task.id}.repair-{repair_attempts}.patch", repair_patch)
        repair_validation = _validate_patch_for_task(repair_patch, task, policy)
        if not repair_validation.ok:
            if _is_major_patch_reason(repair_validation.reason):
                return _block_for_approval(task, loader, artifacts, repair_validation.reason, repair_validation.changed_files)
            return _fail(
                task,
                loader,
                artifacts,
                repair_validation.reason,
                repair_validation.changed_files,
                failure_stage="repair_patch_validation",
                repair_attempts=repair_attempts,
            )
        try:
            apply_unified_patch(workspace_root, repair_patch)
        except Exception as exc:
            return _fail(
                task,
                loader,
                artifacts,
                str(exc),
                repair_validation.changed_files,
                failure_stage="repair_patch_apply",
                repair_attempts=repair_attempts,
            )
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
    _write_markdown_report(
        artifacts,
        task,
        status,
        validation.changed_files,
        checks,
        report["reason"],
        repair_attempts=repair_attempts,
    )

    if status == "done":
        try:
            runtime = _load_runtime(root)
            integration = _integrate_task(root, task, workspace_root, report, runtime)
            if integration:
                report["integration"] = integration
                artifacts.write_json(f"reports/{task.id}.json", report)
        except Exception as exc:
            report["integration"] = {"error": str(exc)}
            artifacts.write_json(f"reports/{task.id}.json", report)

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
