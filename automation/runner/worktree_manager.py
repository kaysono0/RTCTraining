from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Worktree:
    path: Path
    relative_path: str
    branch: str


class WorktreeManager:
    def __init__(self, root: Path):
        self.root = root
        self.base = root / ".automation/worktrees"

    def create(self, task_id: str) -> Worktree:
        self._ensure_git_repo()
        self.base.mkdir(parents=True, exist_ok=True)
        path = self.base / task_id
        if path.exists():
            raise RuntimeError(f"worktree already exists: {path.relative_to(self.root)}")
        branch = f"automation/{task_id}"
        result = subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(path), "HEAD"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "git worktree add failed"
            raise RuntimeError(message)
        return Worktree(path=path, relative_path=str(path.relative_to(self.root)), branch=branch)

    def _ensure_git_repo(self) -> None:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("worktree mode requires a git repository")
        if Path(result.stdout.strip()) != self.root:
            raise RuntimeError("worktree mode must run from the repository root")
