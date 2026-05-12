# Real Low-Risk Catalog Task Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one realistic low-risk automation catalog task and use it to validate the full replenish -> run -> report pipeline end to end.

**Architecture:** Keep the change narrow. The only new production entry point is a catalog recipe that targets the automation runner's report path. The task itself should touch one runner module and its tests, which gives us a real code-change smoke without expanding into unrelated subsystems. Documentation should mention the new catalog entry so the task catalog and the docs stay aligned.

**Tech Stack:** JSON task catalog, Python `pytest`, existing RTCTraining automation runner, Markdown docs.

---

### Task 1: Add a Real Low-Risk Catalog Recipe

**Files:**
- Modify: `automation/config/task_catalog.json`
- Modify: `tests/test_task_supply.py`

- [ ] **Step 1: Add the new catalog recipe**

Add this recipe to the catalog array after the existing two entries:

```json
{
  "id": "report-baseline-summary",
  "title": "补全任务报告的 baseline 摘要",
  "goal": "让自动化任务报告在 Markdown 中展示 baseline 摘要、context_files 和 required_checks，方便回看每次执行的输入与边界。",
  "context_files": [
    "automation/runner/orchestrator.py",
    "tests/test_automation_runner.py",
    "docs/automation/RTCTraining_内部自主开发Agent.md"
  ],
  "allowed_paths": [
    "automation/runner/orchestrator.py",
    "tests/test_automation_runner.py",
    "docs/automation/RTCTraining_内部自主开发Agent.md"
  ],
  "acceptance": [
    "Markdown 任务报告新增 baseline 摘要。",
    "报告中能看出 context_files 和 required_checks 的边界。",
    "自动化 runner 测试通过。"
  ],
  "required_checks": [
    ".venv/bin/python -m pytest tests/test_automation_runner.py -v"
  ],
  "mode": "worktree",
  "risk_level": "low",
  "max_instances": 1
}
```

- [ ] **Step 2: Update the catalog test expectation**

Update `tests/test_task_supply.py` so the repository catalog assertion expects the third recipe:

```python
assert [recipe["id"] for recipe in catalog["recipes"]] == [
    "context-contract-docs",
    "task-supply-regression",
    "report-baseline-summary",
]
```

Also keep the per-recipe assertions for `mode`, `risk_level`, and `max_instances`.

- [ ] **Step 3: Run the focused test file**

Run:

```bash
.venv/bin/python -m pytest tests/test_task_supply.py -v
```

Expected:

```text
4 passed
```

### Task 2: Sync the Automation Docs

**Files:**
- Modify: `docs/automation/RTCTraining_内部自主开发Agent.md`
- Modify: `docs/RTCTraining_项目开发文档.md`

- [ ] **Step 1: Mention the new catalog task in the docs**

Update the catalog description so it reflects that the default low-risk catalog now includes a report-summary task in addition to the docs sync and regression tasks.

Suggested text:

```markdown
- 仓库默认 catalog 以低风险 docs sync / regression test / report baseline summary 任务作为起点，先验证供给链路，再逐步扩展到更多开发任务。
```

- [ ] **Step 2: Run the docs-related test slice**

Run:

```bash
.venv/bin/python -m pytest tests/test_automation_runner.py tests/test_task_supply.py -v
```

Expected:

```text
21 passed
```

### Task 3: Smoke the Full Loop

**Files:**
- No source edits expected; this step validates the new catalog entry through the runner.

- [ ] **Step 1: Replenish ready tasks**

Run:

```bash
.venv/bin/python -m automation.runner.task_cli replenish
```

Expected:

```text
automation/tasks/ready/report-baseline-summary.json
```

- [ ] **Step 2: Run one autonomous task**

Run:

```bash
.venv/bin/python -m automation.runner.orchestrator run-continuous --max-tasks 1 --poll-interval-seconds 0
```

Expected:

```text
[{"task_id":"report-baseline-summary","status":"done",...}]
```

- [ ] **Step 3: Inspect the generated report**

Confirm the JSON and Markdown reports exist under `automation/artifacts/reports/` and show:

```text
- baseline summary
- changed_files
- checks
```

