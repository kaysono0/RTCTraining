# Codex Context Transfer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Codex bridge use a canonical phase-aware request contract and record compact phase summaries in transcript.

**Architecture:** Keep the current command gateway shape, but normalize its payload before rendering the prompt. Add explicit phase-specific prompt sections for `plan`, `develop`, and `repair`, and emit a structured input summary event at run start. The bridge still returns unified diffs for code changes; the new contract only makes the context explicit and replayable.

**Tech Stack:** Python 3.11, `pytest`, existing `automation.runner` modules, JSONL transcript artifacts.

---

### Task 1: Define the canonical phase contract in `codex_bridge`

**Files:**
- Modify: `automation/runner/codex_bridge.py`
- Test: `tests/test_codex_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
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
    assert "Accepted plan" not in plan_prompt

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_codex_bridge.py -v`
Expected: FAIL because the current prompt does not expose phase-specific sections yet.

- [ ] **Step 3: Write minimal implementation**

Add helpers in `automation/runner/codex_bridge.py` that normalize `task`, `plan`, and `failed_checks` into a phase-aware contract and render explicit `plan`, `develop`, and `repair` sections.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_codex_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add automation/runner/codex_bridge.py tests/test_codex_bridge.py
git commit -m "feat: define phase-aware codex context contract"
```

### Task 2: Record phase-aware input summaries in transcript

**Files:**
- Modify: `automation/runner/codex_bridge.py`
- Test: `tests/test_codex_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_codex_records_phase_input_summary(monkeypatch, tmp_path):
    worktree = tmp_path / "worktree"

    monkeypatch.setattr(codex_bridge, "_git_toplevel", lambda root: tmp_path)
    monkeypatch.setattr(codex_bridge, "_prepare_worktree", lambda root, task_id: worktree)
    monkeypatch.setattr(codex_bridge, "_cleanup_worktree", lambda root, worktree_path: None)

    class FakeStdin:
        def __init__(self):
            self.buffer = []

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
                "goal": "Repair the docs change",
                "title": "Repair the docs change",
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
    assert '"phase": "repair"' in transcript
    assert '"repair_attempt": 2' in transcript
    assert '"context_files": ["docs/a.md"]' in transcript
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_codex_bridge.py -v`
Expected: FAIL because transcript currently does not record a phase summary.

- [ ] **Step 3: Write minimal implementation**

Add a compact `codex_exec_start` input summary event that records `phase`, `task_id`, `context_files`, `allowed_paths`, `required_checks`, baseline digest, and repair metadata.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_codex_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add automation/runner/codex_bridge.py tests/test_codex_bridge.py
git commit -m "feat: record codex phase input summaries"
```

### Task 3: Sync the protocol into docs and verify the full suite

**Files:**
- Modify: `docs/automation/RTCTraining_内部自主开发Agent.md`
- Modify: `docs/RTCTraining_项目开发文档.md`
- Test: `.venv/bin/python -m pytest tests/test_automation_runner.py tests/test_codex_bridge.py -v`

- [ ] **Step 1: Write the failing test**

No new code test is required here. Confirm the docs no longer describe a generic prompt and instead name the phase-specific templates.

- [ ] **Step 2: Run the verification suite**

Run: `.venv/bin/python -m pytest tests/test_automation_runner.py tests/test_codex_bridge.py -v`
Expected: PASS after the code and doc updates from Tasks 1 and 2.

- [ ] **Step 3: Update the docs**

Update the bridge description to explain:

- `plan` receives the task contract and baseline summary.
- `develop` receives the accepted plan plus the task contract.
- `repair` receives the failed checks and repair attempt metadata.
- The transcript stores a compact phase input summary.

- [ ] **Step 4: Commit**

```bash
git add docs/automation/RTCTraining_内部自主开发Agent.md docs/RTCTraining_项目开发文档.md
git commit -m "docs: describe codex phase input contract"
```
