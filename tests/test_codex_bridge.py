from __future__ import annotations

import json
import io
import subprocess
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

from automation.runner import codex_bridge


def test_build_prompt_includes_task_plan_and_failed_checks():
    prompt = codex_bridge.build_prompt(
        {
            "phase": "repair",
            "task": {"id": "task-1", "goal": "Fix the empty state"},
            "plan": {"summary": "Inspect empty state and patch the template"},
            "failed_checks": [{"command": "pytest tests/test_ui_routes.py -v", "status": "failed"}],
        }
    )

    assert "Phase: repair" in prompt
    assert "Allowed paths:" in prompt
    assert "Acceptance criteria:" in prompt
    assert '"goal": "Fix the empty state"' in prompt
    assert '"summary": "Inspect empty state and patch the template"' in prompt
    assert '"status": "failed"' in prompt
    assert "Leave the working tree dirty" in prompt


def test_build_prompt_has_phase_specific_sections():
    plan_prompt = codex_bridge.build_prompt(
        {
            "phase": "plan",
            "task": {
                "id": "task-1",
                "title": "Write a plan",
                "goal": "Plan the docs change",
                "context_files": ["docs/a.md"],
                "allowed_paths": ["docs/a.md"],
                "forbidden_paths": [],
                "acceptance": ["A plan is produced."],
                "required_checks": ["pytest tests/test_codex_bridge.py -v"],
                "risk_level": "low",
                "mode": "worktree",
                "baseline": {
                    "kind": "file-manifest",
                    "digest": "abc",
                    "files": [],
                    "patterns": ["docs/a.md"],
                },
            },
            "plan": {},
        }
    )
    assert "Phase: plan" in plan_prompt
    assert "Ask for a concise plan object only." in plan_prompt
    assert "Accepted plan:" not in plan_prompt

    develop_prompt = codex_bridge.build_prompt(
        {
            "phase": "develop",
            "task": {
                "id": "task-1",
                "title": "Write code",
                "goal": "Implement the docs change",
                "context_files": ["docs/a.md"],
                "allowed_paths": ["docs/a.md"],
                "forbidden_paths": [],
                "acceptance": ["The docs are updated."],
                "required_checks": ["pytest tests/test_codex_bridge.py -v"],
                "risk_level": "low",
                "mode": "worktree",
                "baseline": {
                    "kind": "file-manifest",
                    "digest": "abc",
                    "files": [],
                    "patterns": ["docs/a.md"],
                },
            },
            "plan": {"summary": "Edit docs", "files_to_change": ["docs/a.md"]},
        }
    )
    assert "Phase: develop" in develop_prompt
    assert "Accepted plan:" in develop_prompt
    assert "Required checks:" in develop_prompt

    repair_prompt = codex_bridge.build_prompt(
        {
            "phase": "repair",
            "task": {
                "id": "task-1",
                "title": "Repair docs",
                "goal": "Fix the failed docs change",
                "context_files": ["docs/a.md"],
                "allowed_paths": ["docs/a.md"],
                "forbidden_paths": [],
                "acceptance": ["The docs are updated."],
                "required_checks": ["pytest tests/test_codex_bridge.py -v"],
                "risk_level": "low",
                "mode": "worktree",
                "baseline": {
                    "kind": "file-manifest",
                    "digest": "abc",
                    "files": [],
                    "patterns": ["docs/a.md"],
                },
            },
            "plan": {"summary": "Edit docs", "files_to_change": ["docs/a.md"]},
            "failed_checks": [{"command": "pytest tests/test_codex_bridge.py -v", "status": "failed"}],
            "repair_attempt": 1,
        }
    )
    assert "Phase: repair" in repair_prompt
    assert "Failed checks JSON:" in repair_prompt
    assert "repair_attempt" not in repair_prompt


def test_prepare_worktree_links_repo_venv(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "tracked.txt").write_text("initial\n", encoding="utf-8")
    (root / ".venv" / "bin").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "rtc-training@example.test"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "RTCTraining Test"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True, text=True)
    (root / "tracked.txt").write_text("updated\n", encoding="utf-8")
    (root / "untracked.txt").write_text("new file\n", encoding="utf-8")

    result = codex_bridge._prepare_worktree(root, "task-1")

    # git worktree add checks out committed state, not dirty working tree
    assert (result / "tracked.txt").read_text(encoding="utf-8") == "initial\n"
    assert not (result / "untracked.txt").exists()
    assert (result / ".venv").is_symlink()


def test_run_codex_invokes_codex_exec_and_returns_git_diff(monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: worktree)
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)
    monkeypatch.setenv("RTC_AUTOMATION_CODEX_BIN", "codex")
    monkeypatch.setenv("RTC_AUTOMATION_CODEX_MODEL", "gpt-5.4")
    monkeypatch.setenv("RTC_AUTOMATION_CODEX_PROFILE", "default")

    class FakeStdin:
        def __init__(self):
            self.parts: list[str] = []

        def write(self, text):
            self.parts.append(text)

        def close(self):
            return None

        def getvalue(self):
            return "".join(self.parts)

    class FakeProc:
        def __init__(self):
            self.stdin = FakeStdin()
            self.stdout = io.StringIO("codex output\n")
            self.stderr = io.StringIO("startup line\ndiff --git a/README.md b/README.md\n")
            self.returncode = 0
            self.killed = False

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.killed = True

    fake_proc = FakeProc()

    def fake_popen(args, **kwargs):
        calls.append((tuple(args), kwargs))
        return fake_proc

    def fake_run(args, **kwargs):
        calls.append((tuple(args), kwargs))
        if args[:2] == ["git", "-C"]:
            if args[3:5] == ["add", "-A"]:
                return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[3:5] == ["diff", "--cached"]:
                if "--name-only" in args:
                    return CompletedProcess(args=args, returncode=0, stdout="README.md\n", stderr="")
                return CompletedProcess(args=args, returncode=0, stdout="diff --git a/foo b/foo\n", stderr="")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(codex_bridge.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_bridge.subprocess, "run", fake_run)

    diff = codex_bridge.run_codex({"phase": "develop", "task": {"id": "task-1"}, "plan": {}}, Path("."))

    assert diff == "diff --git a/foo b/foo\n"
    codex_call = next(args for args, _ in calls if args[:2] == ("zsh", "-lc"))
    assert "source ~/.zshrc &&" in codex_call[2]
    assert "codex exec" in codex_call[2]
    assert "--ephemeral" in codex_call[2]
    assert "--full-auto" in codex_call[2]
    assert "--ignore-user-config" in codex_call[2]
    assert "--skip-git-repo-check" in codex_call[2]
    assert "--model gpt-5.4" in codex_call[2]
    assert "--profile default" in codex_call[2]
    assert codex_call[2].endswith(" -")
    assert "Phase: develop" in fake_proc.stdin.getvalue()

    transcript = (tmp_path / "automation/artifacts/transcripts/task-1.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in transcript]
    assert events[0]["type"] == "codex_exec_start"
    assert events[-1]["type"] == "codex_diff"
    event_types = {event["type"] for event in events}
    assert {"codex_exec_stdout", "codex_exec_stderr", "codex_exec_finish", "codex_diff"} <= event_types
    finish = next(event for event in events if event["type"] == "codex_exec_finish")
    assert finish["returncode"] == 0
    assert finish["stdout"] == "codex output\n"
    assert any(event["type"] == "codex_exec_stderr" and event["chunk"] == "startup line\n" for event in events)
    diff_event = next(event for event in events if event["type"] == "codex_diff")
    assert diff_event["has_changes"] is True
    assert diff_event["local_files_changed"] is True
    assert diff_event["changed_files"] == ["README.md"]
    assert diff_event["codex_output_has_patch"] is True
    assert diff_event["exported_patch"] is True


def test_run_codex_records_timeout_event(monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: worktree)
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)
    monkeypatch.setattr(codex_bridge, "_codex_timeout_seconds", lambda: 5)

    class FakeProc:
        def __init__(self):
            self.stdin = io.StringIO()
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("still running\n")
            self.returncode = 0

        def wait(self, timeout=None):
            if timeout is not None:
                raise TimeoutExpired(cmd=["codex", "exec"], timeout=timeout, output=b"", stderr=b"still running")
            return self.returncode

        def kill(self):
            return None

    fake_proc = FakeProc()

    def fake_popen(args, **kwargs):
        return fake_proc

    def fake_run(args, **kwargs):
        if args[:2] == ["git", "-C"] and args[3:5] == ["status", "--porcelain"]:
            return CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if args[:2] == ["git", "-C"]:
            raise AssertionError("git diff should not run after timeout")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(codex_bridge.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_bridge.subprocess, "run", fake_run)

    try:
        codex_bridge.run_codex({"phase": "develop", "task": {"id": "task-timeout"}, "plan": {}}, Path("."))
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "timed out" in str(exc)

    transcript = (tmp_path / "automation/artifacts/transcripts/task-timeout.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in transcript]
    assert events[0]["type"] == "codex_exec_start"
    assert events[-1]["type"] == "codex_exec_timeout"
    assert any(event["type"] == "codex_exec_stderr" and event["chunk"] == "still running\n" for event in events)
    timeout_event = events[-1]
    assert timeout_event["stdout"] == ""
    assert timeout_event["stderr"] == "still running\n"
    assert timeout_event["local_files_changed"] is False
    assert timeout_event["changed_files"] == []
    assert timeout_event["codex_output_has_patch"] is False


def test_run_codex_records_phase_input_summary(monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: worktree)
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)

    class FakeStdin:
        def __init__(self):
            self.buffer: list[str] = []

        def write(self, text):
            self.buffer.append(text)

        def close(self):
            return None

    class FakeProc:
        def __init__(self):
            self.stdin = FakeStdin()
            self.stdout = io.StringIO("diff --git a/README.md b/README.md\n")
            self.stderr = io.StringIO("")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(codex_bridge.subprocess, "Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr(
        codex_bridge.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args=args[0], returncode=0, stdout="README.md\n", stderr=""),
    )

    codex_bridge.run_codex(
        {
            "phase": "repair",
            "repair_attempt": 2,
            "task": {
                "id": "task-1",
                "title": "Repair the docs change",
                "goal": "Repair the docs change",
                "context_files": ["docs/a.md"],
                "allowed_paths": ["docs/a.md"],
                "forbidden_paths": [],
                "acceptance": ["Docs updated."],
                "required_checks": ["pytest tests/test_codex_bridge.py -v"],
                "risk_level": "low",
                "mode": "worktree",
                "baseline": {
                    "kind": "file-manifest",
                    "digest": "abc",
                    "files": [],
                    "patterns": ["docs/a.md"],
                },
            },
            "plan": {"summary": "Edit docs", "files_to_change": ["docs/a.md"]},
            "failed_checks": [{"command": "pytest tests/test_codex_bridge.py -v", "status": "failed"}],
        },
        Path("."),
    )

    transcript = (tmp_path / "automation/artifacts/transcripts/task-1.jsonl").read_text(encoding="utf-8")
    assert '"type": "codex_exec_start"' in transcript
    assert '"input_summary"' in transcript
    assert '"phase": "repair"' in transcript
    assert '"repair_attempt": 2' in transcript
    assert '"context_files": ["docs/a.md"]' in transcript


def test_run_codex_uses_provided_workspace_root_instead_of_temp_worktree(monkeypatch, tmp_path):
    """When workspace_root is in the payload, codex bridge should use it directly
    instead of creating a new temp worktree via _prepare_worktree."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "rtc-training@example.test"], cwd=workspace, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "RTCTraining Test"], cwd=workspace, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=workspace, check=True, capture_output=True, text=True)

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: (_ for _ in ()).throw(RuntimeError("_prepare_worktree should not be called")))
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)

    class FakeProc:
        def __init__(self):
            self.stdin = io.StringIO()
            self.stdout = io.StringIO("diff --git a/sample.txt b/sample.txt\n--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-initial\n+updated\n")
            self.stderr = io.StringIO("")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    run_calls: list[list[str]] = []
    def fake_run(args, **kwargs):
        nonlocal run_calls
        run_calls.append(args)
        if "--binary" in args:
            return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="diff --git a/sample.txt b/sample.txt\n--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-initial\n+updated\n", stderr="")
        if "--name-only" in args:
            return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="sample.txt\n", stderr="")
        return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(codex_bridge.subprocess, "Popen", lambda *args, **kwargs: FakeProc())
    monkeypatch.setattr(codex_bridge.subprocess, "run", fake_run)

    diff = codex_bridge.run_codex(
        {
            "phase": "develop",
            "workspace_root": str(workspace),
            "task": {"id": "task-workspace", "goal": "use workspace"},
            "plan": {},
        },
        Path("."),
    )

    assert "sample.txt" in diff
    assert "+updated" in diff


def test_run_codex_uses_claude_backend_when_bin_is_claude(monkeypatch, tmp_path):
    """When RTC_AUTOMATION_CODEX_BIN=claude, the bridge uses claude execute --print
    instead of codex exec --ephemeral --full-auto ..."""
    monkeypatch.setenv("RTC_AUTOMATION_CODEX_BIN", "claude")
    monkeypatch.setenv("RTC_AUTOMATION_CODEX_MODEL", "claude-sonnet-4-6")
    worktree = tmp_path / "worktree"

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: worktree)
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)

    class FakeProc:
        def __init__(self):
            self.stdin = io.StringIO()
            self.stdout = io.StringIO("diff --git a/README.md b/README.md\n")
            self.stderr = io.StringIO("")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def fake_popen(args, **kwargs):
        calls.append((tuple(args), kwargs))
        return FakeProc()

    def fake_run(args, **kwargs):
        calls.append((tuple(args), kwargs))
        if "--name-only" in args:
            return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="README.md\n", stderr="")
        if "--binary" in args or "--cached" in args:
            return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="diff --git a/README.md b/README.md\n", stderr="")
        return __import__("subprocess").CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(codex_bridge.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_bridge.subprocess, "run", fake_run)

    codex_bridge.run_codex(
        {"phase": "develop", "task": {"id": "task-claude"}, "plan": {}},
        Path("."),
    )

    cli_call = next(args for args, _ in calls if args[:2] == ("zsh", "-lc"))
    cmd = cli_call[2]
    assert "claude execute" in cmd, f"expected claude execute in command, got: {cmd}"
    assert "--print" in cmd
    assert "--ephemeral" not in cmd
    assert "--full-auto" not in cmd
    assert "--model claude-sonnet-4-6" in cmd
    # claude backend reads from stdin implicitly; no trailing -
    assert not cmd.rstrip().endswith(" -"), f"claude should not have trailing '-'"
