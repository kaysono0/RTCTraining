from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from automation.runner.transcript_watch import load_transcript, summarize_transcript, wait_for_quiet_transcript


def test_summarize_transcript_detects_patch_and_reconnecting():
    events = [
        {"type": "codex_exec_stderr", "chunk": "ERROR: Reconnecting... 5/5\n"},
        {"type": "codex_diff", "local_files_changed": True, "exported_patch": True, "codex_output_has_patch": True},
    ]

    summary = summarize_transcript(events)

    assert summary.event_count == 2
    assert summary.saw_reconnecting_5_of_5 is True
    assert summary.local_files_changed is True
    assert summary.exported_patch is True
    assert summary.codex_output_has_patch is True
    assert summary.last_event_type == "codex_diff"


def test_wait_for_quiet_transcript_returns_after_growth_stops(tmp_path):
    transcript = tmp_path / "sample.jsonl"

    def writer():
        transcript.write_text(
            json.dumps({"type": "codex_exec_stderr", "chunk": "ERROR: Reconnecting... 5/5\n"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        time.sleep(0.05)
        transcript.write_text(
            transcript.read_text(encoding="utf-8")
            + json.dumps(
                {"type": "codex_diff", "local_files_changed": False, "exported_patch": False, "codex_output_has_patch": False},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    thread = threading.Thread(target=writer)
    thread.start()
    summary = wait_for_quiet_transcript(transcript, quiet_seconds=0.1, poll_interval_seconds=0.01)
    thread.join(timeout=1)

    assert summary.event_count == 2
    assert summary.saw_reconnecting_5_of_5 is True
    assert summary.local_files_changed is False
    assert summary.exported_patch is False
    assert summary.codex_output_has_patch is False
    assert summary.last_event_type == "codex_diff"
    assert len(load_transcript(transcript)) == 2


def test_watch_script_runs_directly(tmp_path):
    transcript = tmp_path / "sample.jsonl"
    transcript.write_text(
        json.dumps({"type": "codex_diff", "local_files_changed": True, "exported_patch": True, "codex_output_has_patch": True})
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/watch_codex_transcript.py",
            str(transcript),
            "--quiet-seconds",
            "0.01",
            "--poll-interval-seconds",
            "0.01",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"exported_patch": true' in result.stdout
