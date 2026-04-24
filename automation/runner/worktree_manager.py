from __future__ import annotations

import shutil
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
        self.root = root.resolve()
        self.base = self.root / ".automation/worktrees"

    def create(self, task_id: str) -> Worktree:
        self._ensure_git_repo()
        self.base.mkdir(parents=True, exist_ok=True)
        path = self.base / task_id
        if path.exists():
            raise RuntimeError(f"worktree already exists: {path.relative_to(self.root)}")
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(path)],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            shutil.rmtree(path, ignore_errors=True)
            raise
        self._link_venv(path)
        head = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return Worktree(
            path=path,
            relative_path=str(path.relative_to(self.root)),
            branch=head,
        )

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
        if Path(result.stdout.strip()).resolve() != self.root:
            raise RuntimeError("worktree mode must run from the repository root")

    def _link_venv(self, snapshot_root: Path) -> None:
        venv = self.root / ".venv"
        if not venv.exists():
            return
        link = snapshot_root / ".venv"
        if not link.exists():
            link.symlink_to(venv, target_is_directory=True)

