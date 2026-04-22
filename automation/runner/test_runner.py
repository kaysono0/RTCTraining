from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from automation.runner.artifact_store import ArtifactStore
from automation.runner.policies import Policy


@dataclass(frozen=True)
class CheckResult:
    command: str
    status: str
    exit_code: int
    duration_ms: int
    log_path: str


class TestRunner:
    def __init__(self, root: Path, policy: Policy, artifacts: ArtifactStore, *, command_root: Path | None = None):
        self.root = root
        self.command_root = command_root or root
        self.policy = policy
        self.artifacts = artifacts

    def run_checks(self, task_id: str, commands: list[str]) -> list[CheckResult]:
        results: list[CheckResult] = []
        for index, command in enumerate(commands, start=1):
            started = time.monotonic()
            if not self.policy.command_allowed(command):
                result = subprocess.CompletedProcess(shlex.split(command), 126, "", "command not allowed")
            else:
                parts = shlex.split(command)
                if parts and parts[0].startswith(".venv/"):
                    parts[0] = str(self.command_root / parts[0])
                result = subprocess.run(
                    parts,
                    cwd=self.root,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.policy.command_timeout_seconds,
                )
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "passed" if result.returncode == 0 else "failed"
            log = {
                "command": command,
                "status": status,
                "exit_code": result.returncode,
                "duration_ms": duration_ms,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            log_path = self.artifacts.write_json(f"test-runs/{task_id}/{index:03d}.json", log)
            results.append(
                CheckResult(
                    command=command,
                    status=status,
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                    log_path=str(log_path.relative_to(self.command_root)),
                )
            )
        return results
