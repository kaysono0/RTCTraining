from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "id",
    "goal",
    "context_files",
    "allowed_paths",
    "forbidden_paths",
    "acceptance",
    "required_checks",
    "risk_level",
    "mode",
}
BASELINE_FIELDS = {"kind", "digest", "files", "patterns"}


class TaskError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def risk_level(self) -> str:
        return str(self.data["risk_level"])


class TaskLoader:
    def __init__(self, root: Path):
        self.root = root
        self.tasks_dir = root / "automation/tasks"

    def ensure(self) -> None:
        for name in ("ready", "running", "done", "failed", "blocked"):
            (self.tasks_dir / name).mkdir(parents=True, exist_ok=True)

    def next_ready(self) -> Task | None:
        self.ensure()
        ready = sorted((self.tasks_dir / "ready").glob("*.json"))
        if not ready:
            return None
        return self.load(ready[0])

    def load(self, path: Path) -> Task:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.validate(data)
        return Task(path=path, data=data)

    def validate(self, data: dict[str, Any]) -> None:
        missing = sorted(REQUIRED_FIELDS - data.keys())
        if missing:
            raise TaskError(f"task is missing required fields: {', '.join(missing)}")
        task_id = str(data["id"])
        if not task_id or "/" in task_id or ".." in task_id:
            raise TaskError("task id must be a plain file-safe id")
        for field in ("context_files", "allowed_paths", "forbidden_paths", "acceptance", "required_checks"):
            if not isinstance(data[field], list):
                raise TaskError(f"{field} must be a list")
        if not data["allowed_paths"]:
            raise TaskError("allowed_paths must not be empty")
        baseline = data.get("baseline")
        if baseline is not None:
            if not isinstance(baseline, dict):
                raise TaskError("baseline must be an object")
            missing_baseline = sorted(BASELINE_FIELDS - baseline.keys())
            if missing_baseline:
                raise TaskError(f"baseline is missing required fields: {', '.join(missing_baseline)}")
            if baseline.get("kind") != "file-manifest":
                raise TaskError("baseline has unsupported kind")
            if not isinstance(baseline.get("digest"), str):
                raise TaskError("baseline.digest must be a string")
            if not isinstance(baseline.get("files"), list):
                raise TaskError("baseline.files must be a list")
            if "patterns" in baseline and not isinstance(baseline.get("patterns"), list):
                raise TaskError("baseline.patterns must be a list")
        for field in ("context_files", "allowed_paths", "forbidden_paths"):
            for value in data[field]:
                if Path(str(value)).is_absolute() or ".." in Path(str(value)).parts:
                    raise TaskError(f"{field} contains unsafe path: {value}")

    def move(self, task: Task, state: str) -> Path:
        self.ensure()
        target = self.tasks_dir / state / f"{task.id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if task.path.exists():
            shutil.move(str(task.path), target)
        else:
            target.write_text(json.dumps(task.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
