from __future__ import annotations

from typing import Any

from automation.runner.artifact_store import ArtifactStore


class StubModelGateway:
    """Deterministic model gateway used by the first local harness and tests."""

    def __init__(self, artifacts: ArtifactStore):
        self.artifacts = artifacts

    def plan(self, task: dict[str, Any]) -> dict[str, Any]:
        plan = {
            "summary": task["goal"],
            "files_to_change": task["allowed_paths"],
            "tests_to_run": task["required_checks"],
            "risk_notes": [f"risk_level={task['risk_level']}"],
        }
        self.artifacts.append_transcript(str(task["id"]), {"type": "plan", "content": plan})
        return plan

    def develop(self, task: dict[str, Any], plan: dict[str, Any]) -> str:
        patch = str(task.get("stub_patch", ""))
        self.artifacts.append_transcript(
            str(task["id"]),
            {"type": "develop", "plan_summary": plan["summary"], "patch_bytes": len(patch.encode("utf-8"))},
        )
        return patch
