from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automation.runner.task_baseline import build_task_baseline
from automation.runner.task_loader import TaskLoader


DEFAULT_FORBIDDEN_PATHS = ["data/**", "certs/**", ".env", ".venv/**"]


@dataclass(frozen=True)
class TaskSupplyConfig:
    enabled: bool
    min_ready_tasks: int
    max_ready_tasks: int
    catalog_path: Path


@dataclass(frozen=True)
class TaskRecipe:
    id: str
    title: str
    goal: str
    context_files: list[str]
    allowed_paths: list[str]
    acceptance: list[str]
    required_checks: list[str]
    mode: str = "worktree"
    risk_level: str = "low"
    forbidden_paths: list[str] | None = None
    max_repair_attempts: int = 1
    max_instances: int = 1
    approved_by_user: bool | None = None
    stub_patch: str | None = None
    stub_repair_patches: list[str] | None = None

    def build_task(self, root: Path, task_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": task_id,
            "title": self.title,
            "goal": self.goal,
            "context_files": list(self.context_files),
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths or DEFAULT_FORBIDDEN_PATHS),
            "acceptance": list(self.acceptance),
            "required_checks": list(self.required_checks),
            "risk_level": self.risk_level,
            "mode": self.mode,
            "max_repair_attempts": self.max_repair_attempts,
            "supplied_from": self.id,
            "baseline": build_task_baseline(root, list(self.context_files), list(self.allowed_paths)),
        }
        if self.approved_by_user is not None:
            payload["approved_by_user"] = self.approved_by_user
        if self.stub_patch is not None:
            payload["stub_patch"] = self.stub_patch
        if self.stub_repair_patches is not None:
            payload["stub_repair_patches"] = list(self.stub_repair_patches)
        return payload


class TaskSupplyManager:
    def __init__(self, root: Path):
        self.root = root
        self.config_path = root / "automation/config/task_supply.json"

    def replenish(self) -> list[str]:
        config = self._load_config()
        if config is None or not config.enabled:
            return []
        loader = TaskLoader(self.root)
        loader.ensure()
        ready_dir = self.root / "automation/tasks/ready"
        ready_count = len(list(ready_dir.glob("*.json")))
        if ready_count >= config.max_ready_tasks:
            return []
        recipes = self._load_catalog(config.catalog_path)
        if not recipes:
            return []
        existing_ids = self._task_ids_in_states(loader)
        created: list[str] = []
        while ready_count < config.min_ready_tasks and ready_count < config.max_ready_tasks:
            progress = False
            for recipe in recipes:
                if ready_count >= config.min_ready_tasks or ready_count >= config.max_ready_tasks:
                    break
                task_id = self._next_task_id(recipe, existing_ids)
                if task_id is None:
                    continue
                payload = recipe.build_task(self.root, task_id)
                path = ready_dir / f"{task_id}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                created.append(task_id)
                existing_ids.add(task_id)
                ready_count += 1
                progress = True
            if not progress:
                break
        return created

    def _load_config(self) -> TaskSupplyConfig | None:
        if not self.config_path.exists():
            return None
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        enabled = bool(data.get("enabled", True))
        min_ready_tasks = max(int(data.get("min_ready_tasks", 1)), 0)
        max_ready_tasks = max(int(data.get("max_ready_tasks", max(min_ready_tasks, 1))), min_ready_tasks)
        catalog_raw = str(data.get("catalog_path", "automation/config/task_catalog.json"))
        catalog_path = self.root / catalog_raw
        return TaskSupplyConfig(enabled, min_ready_tasks, max_ready_tasks, catalog_path)

    def _load_catalog(self, path: Path) -> list[TaskRecipe]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            recipes = data.get("recipes", [])
        else:
            recipes = data
        result: list[TaskRecipe] = []
        for recipe_data in recipes:
            result.append(
                TaskRecipe(
                    id=str(recipe_data["id"]),
                    title=str(recipe_data["title"]),
                    goal=str(recipe_data["goal"]),
                    context_files=[str(value) for value in recipe_data["context_files"]],
                    allowed_paths=[str(value) for value in recipe_data["allowed_paths"]],
                    acceptance=[str(value) for value in recipe_data["acceptance"]],
                    required_checks=[str(value) for value in recipe_data["required_checks"]],
                    mode=str(recipe_data.get("mode", "worktree")),
                    risk_level=str(recipe_data.get("risk_level", "low")),
                    forbidden_paths=[str(value) for value in recipe_data.get("forbidden_paths", DEFAULT_FORBIDDEN_PATHS)],
                    max_repair_attempts=int(recipe_data.get("max_repair_attempts", 1)),
                    max_instances=max(int(recipe_data.get("max_instances", 1)), 1),
                    approved_by_user=recipe_data.get("approved_by_user"),
                    stub_patch=recipe_data.get("stub_patch"),
                    stub_repair_patches=[str(value) for value in recipe_data.get("stub_repair_patches", [])]
                    if recipe_data.get("stub_repair_patches") is not None
                    else None,
                )
            )
        return result

    def _task_ids_in_states(self, loader: TaskLoader) -> set[str]:
        ids: set[str] = set()
        for state in ("ready", "running", "done", "failed", "blocked"):
            for path in (self.root / "automation/tasks" / state).glob("*.json"):
                try:
                    task = loader.load(path)
                except Exception:
                    continue
                ids.add(task.id)
        return ids

    def _next_task_id(self, recipe: TaskRecipe, existing_ids: set[str]) -> str | None:
        if recipe.id not in existing_ids:
            return recipe.id
        for instance in range(2, recipe.max_instances + 1):
            candidate = f"{recipe.id}-{instance}"
            if candidate not in existing_ids:
                return candidate
        return None
