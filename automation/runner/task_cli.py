from __future__ import annotations

import argparse
import json
from pathlib import Path

from automation.runner.task_baseline import build_task_baseline
from automation.runner.task_supply import TaskSupplyManager


DEFAULT_FORBIDDEN_PATHS = ["data/**", "certs/**", ".env", ".venv/**"]


def create_task(
    root: Path,
    *,
    task_id: str,
    title: str,
    goal: str,
    context_files: list[str],
    allowed_paths: list[str],
    acceptance: list[str],
    required_checks: list[str],
    mode: str = "worktree",
    risk_level: str = "low",
    forbidden_paths: list[str] | None = None,
) -> Path:
    payload = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "context_files": context_files,
        "allowed_paths": allowed_paths,
        "forbidden_paths": forbidden_paths or DEFAULT_FORBIDDEN_PATHS,
        "acceptance": acceptance,
        "required_checks": required_checks,
        "risk_level": risk_level,
        "mode": mode,
        "max_repair_attempts": 1,
        "baseline": build_task_baseline(root, context_files, allowed_paths),
    }
    path = root / "automation/tasks/ready" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def approve_task(root: Path, task_id: str) -> Path:
    source = root / "automation/tasks/blocked" / f"{task_id}.json"
    if not source.exists():
        raise FileNotFoundError(f"blocked task does not exist: {task_id}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["approved_by_user"] = True
    target = root / "automation/tasks/ready" / f"{task_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    source.unlink()
    return target


def replenish_tasks(root: Path) -> list[Path]:
    created_ids = TaskSupplyManager(root).replenish()
    return [root / "automation/tasks/ready" / f"{task_id}.json" for task_id in created_ids]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and approve RTCTraining automation tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a ready automation task")
    create.add_argument("--id", required=True, dest="task_id")
    create.add_argument("--title", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--context-files", required=True, help="Comma-separated context paths")
    create.add_argument("--allowed-paths", required=True, help="Comma-separated writable path globs")
    create.add_argument("--acceptance", required=True, help="Comma-separated acceptance items")
    create.add_argument("--required-checks", required=True, help="Comma-separated shell commands")
    create.add_argument("--mode", default="worktree", choices=["patch-only", "worktree"])
    create.add_argument("--risk-level", default="low")

    approve = subparsers.add_parser("approve", help="Approve a blocked task and move it back to ready")
    approve.add_argument("task_id")

    replenish = subparsers.add_parser("replenish", help="Replenish ready tasks from the task supply catalog")

    args = parser.parse_args()
    root = Path(".")
    if args.command == "create":
        path = create_task(
            root,
            task_id=args.task_id,
            title=args.title,
            goal=args.goal,
            context_files=_split_csv(args.context_files),
            allowed_paths=_split_csv(args.allowed_paths),
            acceptance=_split_csv(args.acceptance),
            required_checks=_split_csv(args.required_checks),
            mode=args.mode,
            risk_level=args.risk_level,
        )
        print(path)
        return 0
    if args.command == "approve":
        path = approve_task(root, args.task_id)
        print(path)
        return 0
    if args.command == "replenish":
        paths = replenish_tasks(root)
        for path in paths:
            print(path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
