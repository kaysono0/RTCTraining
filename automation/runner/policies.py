from __future__ import annotations

import fnmatch
import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str = ""


class Policy:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "automation/config/policy.json"
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"missing policy file: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def command_timeout_seconds(self) -> int:
        return int(self.data.get("command_timeout_seconds", 300))

    @property
    def max_patch_bytes(self) -> int:
        return int(self.data.get("max_patch_bytes", 80000))

    @property
    def max_changed_files(self) -> int:
        return int(self.data.get("max_changed_files", 8))

    def evaluate_task(self, task: dict[str, Any]) -> PolicyDecision:
        risk = str(task["risk_level"])
        risk_policy = self.data.get("risk_levels", {}).get(risk)
        if risk_policy is None:
            return PolicyDecision(False, True, f"unknown risk level: {risk}")
        if risk_policy.get("requires_approval") and not task.get("approved_by_user"):
            return PolicyDecision(False, True, "risk level requires approval")
        for context_file in task["context_files"]:
            path = self.root / str(context_file)
            if not path.exists():
                return PolicyDecision(False, False, f"context file does not exist: {context_file}")
        for command in task["required_checks"]:
            if not self.command_allowed(str(command)):
                return PolicyDecision(False, True, f"command requires approval: {command}")
        return PolicyDecision(True, False)

    def command_allowed(self, command: str) -> bool:
        parts = shlex.split(command)
        for prefix in self.data.get("allowed_command_prefixes", []):
            if parts[: len(prefix)] == prefix:
                return True
        return False

    def forbidden_patterns(self, task: dict[str, Any]) -> list[str]:
        return list(self.data.get("global_forbidden_paths", [])) + list(task.get("forbidden_paths", []))


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
