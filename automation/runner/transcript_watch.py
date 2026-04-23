from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptSummary:
    event_count: int
    saw_reconnecting_5_of_5: bool
    local_files_changed: bool
    exported_patch: bool
    codex_output_has_patch: bool
    last_event_type: str


def load_transcript(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def summarize_transcript(events: list[dict[str, Any]]) -> TranscriptSummary:
    saw_reconnecting = False
    local_files_changed = False
    exported_patch = False
    codex_output_has_patch = False
    last_event_type = ""

    for event in events:
        last_event_type = str(event.get("type", ""))
        chunk = str(event.get("chunk", ""))
        if "Reconnecting... 5/5" in chunk:
            saw_reconnecting = True
        if event.get("type") == "codex_diff":
            local_files_changed = bool(event.get("local_files_changed"))
            exported_patch = bool(event.get("exported_patch"))
            codex_output_has_patch = bool(event.get("codex_output_has_patch"))
        if event.get("type") == "codex_exec_timeout":
            local_files_changed = bool(event.get("local_files_changed", local_files_changed))
            exported_patch = bool(event.get("exported_patch", exported_patch))
            codex_output_has_patch = bool(event.get("codex_output_has_patch", codex_output_has_patch))

    return TranscriptSummary(
        event_count=len(events),
        saw_reconnecting_5_of_5=saw_reconnecting,
        local_files_changed=local_files_changed,
        exported_patch=exported_patch,
        codex_output_has_patch=codex_output_has_patch,
        last_event_type=last_event_type,
    )


def wait_for_quiet_transcript(
    path: Path,
    *,
    quiet_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> TranscriptSummary:
    last_size = -1
    quiet_started = time.monotonic()

    while True:
        size = path.stat().st_size if path.exists() else 0
        if size != last_size:
            last_size = size
            quiet_started = time.monotonic()
        elif time.monotonic() - quiet_started >= quiet_seconds:
            return summarize_transcript(load_transcript(path))
        time.sleep(poll_interval_seconds)
