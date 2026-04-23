from __future__ import annotations

import shutil
import subprocess
import tempfile
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
        snapshot_root = Path(tempfile.mkdtemp(prefix=f"rtc-worktree-{task_id}-", dir=str(self.base)))
        try:
            self._copy_snapshot(snapshot_root)
            self._link_venv(snapshot_root)
            self._initialize_git_repo(snapshot_root, task_id)
        except Exception:
            shutil.rmtree(snapshot_root, ignore_errors=True)
            raise
        return Worktree(
            path=snapshot_root,
            relative_path=str(snapshot_root.relative_to(self.root)),
            branch=f"snapshot/{task_id}",
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

    def _copy_snapshot(self, snapshot_root: Path) -> None:
        def ignore(directory: str, names: list[str]) -> set[str]:
            rel = Path(directory).resolve().relative_to(self.root)
            ignored: set[str] = set()
            if rel == Path("."):
                ignored.update({".git", ".venv", ".pytest_cache"})
            if rel == Path("automation"):
                ignored.add("artifacts")
            if rel == Path(".automation"):
                ignored.add("worktrees")
            return ignored

        shutil.copytree(self.root, snapshot_root, dirs_exist_ok=True, symlinks=True, ignore=ignore)

    def _link_venv(self, snapshot_root: Path) -> None:
        venv = self.root / ".venv"
        if not venv.exists():
            return
        link = snapshot_root / ".venv"
        if not link.exists():
            link.symlink_to(venv, target_is_directory=True)

    def _initialize_git_repo(self, snapshot_root: Path, task_id: str) -> None:
        subprocess.run(["git", "init"], cwd=snapshot_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.email", "rtc-training@example.test"],
            cwd=snapshot_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "RTCTraining Snapshot"],
            cwd=snapshot_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "add", "-A"], cwd=snapshot_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", f"snapshot {task_id}"],
            cwd=snapshot_root,
            check=True,
            capture_output=True,
            text=True,
        )
        exclude = snapshot_root / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(".venv\n", encoding="utf-8")
