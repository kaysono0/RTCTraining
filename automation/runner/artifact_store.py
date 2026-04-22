from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.base = root / "automation/artifacts"

    def ensure(self) -> None:
        for name in (
            "approvals",
            "plans",
            "patches",
            "reports",
            "test-runs",
            "transcripts",
        ):
            (self.base / name).mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_text(self, relative_path: str, text: str) -> Path:
        path = self.base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def append_transcript(self, task_id: str, event: dict[str, Any]) -> None:
        path = self.base / "transcripts" / f"{task_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": utc_now_iso(), **event}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
