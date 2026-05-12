# RTCTraining Closed-Loop Development Agent Design

## Goal

Build a constrained, auditable development agent for RTCTraining that can take a low-risk task contract, create an isolated workspace, make code changes, run the required tests, repair failures within a bounded loop, and emit reviewable artifacts.

The agent is not a fully autonomous repository maintainer. It is a task-contract executor. Its authority comes from explicit task JSON, repository policies, command allowlists, path allowlists, and human review.

## Source Context

This design is based on `RTCTraining_整理版.md`, especially these constraints:

- RTCTraining's primary value is the WebRTC experiment loop: connection, stats collection, experiment control, CSV export, Dashboard comparison, and automation task closure.
- `automation/` is an independent low-risk development runner, not part of the WebRTC runtime path.
- The runner should validate path policy, command policy, and task risk before doing work.
- It should produce plan, patch, transcript, task report, and morning summary artifacts.
- It should not modify experimental outputs under `data/`.
- It should prefer minimal necessary validation instead of always running the heaviest tests.

## Non-Goals

- No automatic merge to the main branch.
- No arbitrary command execution.
- No write access outside task-declared paths.
- No production RTC infrastructure such as TURN, SFU, auth, long-term storage, or public deployment.
- No unbounded self-repair loop.
- No hidden state: every model request, response, command, and result must be recorded.

## Recommended Approach

Use a worktree-based closed-loop agent.

Each task runs in its own git worktree. The agent reads a task contract, validates it against repository policy, creates a plan, applies a bounded change, runs required checks, analyzes failures, repairs up to a configured maximum number of attempts, and writes final artifacts. A human then reviews the patch and report.

This is safer than a full autonomous agent and more useful than a patch-only generator. It gives the system a real develop-test-repair loop while preserving auditability.

## High-Level Loop

```text
Task Contract
  -> Policy Gate
  -> Worktree Manager
  -> Context Loader
  -> Planner
  -> Developer
  -> Diff Validator
  -> Test Selector
  -> Test Runner
  -> Failure Analyzer
  -> Repair Loop
  -> Reviewer
  -> Artifact Export
  -> Human Approval
```

## Directory Layout

```text
automation/
├── config/
│   ├── policy.json
│   └── runtime.json
├── prompts/
│   ├── planner.md
│   ├── developer.md
│   ├── failure_analyzer.md
│   └── reviewer.md
├── runner/
│   ├── __init__.py
│   ├── artifact_store.py
│   ├── command_runner.py
│   ├── context_loader.py
│   ├── developer.py
│   ├── diff_validator.py
│   ├── failure_analyzer.py
│   ├── model_gateway.py
│   ├── orchestrator.py
│   ├── planner.py
│   ├── policies.py
│   ├── reviewer.py
│   ├── task_loader.py
│   ├── test_runner.py
│   ├── test_selector.py
│   └── worktree_manager.py
├── tasks/
│   ├── ready/
│   ├── running/
│   ├── done/
│   └── failed/
└── artifacts/
    ├── plans/
    ├── patches/
    ├── reports/
    ├── summaries/
    ├── test-runs/
    └── transcripts/
```

## Task Contract

Tasks live under `automation/tasks/ready/<task_id>.json`.

Required fields:

```json
{
  "id": "fix-dashboard-empty-stats",
  "goal": "Fix Dashboard rendering when stats data is empty.",
  "context_files": [
    "src/dashboard/server.py",
    "src/dashboard/templates/index.html",
    "tests/test_dashboard.py"
  ],
  "allowed_paths": [
    "src/dashboard/**",
    "tests/test_dashboard*.py",
    "docs/**"
  ],
  "forbidden_paths": [
    "data/**",
    "cert.pem",
    "key.pem",
    ".env",
    ".venv/**"
  ],
  "acceptance": [
    "Dashboard returns HTTP 200 when no stats are available.",
    "The page shows an empty state instead of raising an exception.",
    "The dashboard test suite passes."
  ],
  "required_checks": [
    "pytest tests/test_dashboard.py"
  ],
  "optional_checks": [
    "pytest tests/test_dashboard_realtime.py"
  ],
  "risk_level": "low",
  "mode": "worktree",
  "max_repair_attempts": 3
}
```

Optional fields:

- `notes`: human guidance for the agent.
- `linked_docs`: relevant design, API, or testing docs.
- `skip_optional_checks_reason`: explicit reason when optional checks should not run.
- `expected_artifacts`: files the task is expected to produce.

## Policy Model

The repository policy is loaded from `automation/config/policy.json`.

Policy categories:

- `allowed_command_prefixes`: exact command prefixes the runner may execute.
- `global_forbidden_paths`: paths no task may write.
- `risk_levels`: behavior per risk level.
- `max_context_bytes`: upper bound for model context loading.
- `max_patch_bytes`: upper bound for patch application.
- `max_repair_attempts`: default repair limit.

Default risk behavior:

```text
low
  allow planning, patching, required checks, and bounded repair

medium
  allow planning and patch generation
  require human approval before applying patch or running commands

high
  plan only
  no patch application
  no command execution
```

Global forbidden paths:

```text
data/**
automation/artifacts/**
.git/**
.venv/**
cert.pem
key.pem
.env
```

The runner may write into `automation/artifacts/**` only through `ArtifactStore`, not through model-generated patches.

## Core Components

### `task_loader.py`

Reads JSON task contracts from `automation/tasks/ready/`, validates required fields, and moves tasks between `ready`, `running`, `done`, and `failed`.

It rejects:

- missing `id`, `goal`, `acceptance`, `required_checks`, or `risk_level`
- duplicate task IDs
- path traversal such as `../`
- empty `allowed_paths`
- unknown risk levels

### `policies.py`

Loads global policy and evaluates a task against it.

Responsibilities:

- verify every context file is readable and allowed
- verify every required check matches a command allowlist prefix
- merge task `forbidden_paths` with global forbidden paths
- decide whether the task can patch files, run tests, or only produce a plan

### `worktree_manager.py`

Creates and cleans isolated worktrees.

Worktree naming:

```text
.automation/worktrees/<task_id>
```

Branch naming:

```text
automation/<task_id>
```

The worktree manager refuses to run if the base repository has uncommitted changes unless the caller explicitly selects `patch-only` mode.

### `context_loader.py`

Reads only files listed in `context_files` and linked docs that pass policy. It also captures lightweight repository metadata:

- current branch
- git status
- file list under allowed paths
- matching tests from the test selector

It does not load `data/`, certificates, virtualenv files, or artifacts.

### `planner.py`

Asks the model for a short plan in structured JSON.

Required plan fields:

```json
{
  "summary": "One paragraph plan.",
  "files_to_change": ["src/dashboard/server.py"],
  "tests_to_run": ["pytest tests/test_dashboard.py"],
  "risk_notes": ["No data files touched."]
}
```

The plan is rejected if it names files outside `allowed_paths`, omits required checks, or contradicts task risk policy.

### `developer.py`

Asks the model for a unified diff. It does not let the model run commands directly.

The diff is passed to `diff_validator.py` before application.

### `diff_validator.py`

Parses the unified diff and enforces:

- every modified file is under `allowed_paths`
- no file matches `forbidden_paths`
- no binary patch
- no deletion of broad directories
- patch size under policy limit
- no modification to `automation/artifacts/**`

### `test_selector.py`

Adds recommended checks based on changed paths, while always preserving task-required checks.

Recommended mapping:

```text
src/webrtc/mesh_handlers.py
src/webrtc/chat_server.py
  -> pytest tests/test_mesh_signaling.py
  -> pytest tests/test_mesh_room_lifecycle.py

src/webrtc/stats_store.py
src/webrtc/stats_handlers.py
  -> pytest tests/test_unit.py
  -> pytest tests/test_rtcp_analysis.py

src/dashboard/**
  -> pytest tests/test_dashboard.py
  -> pytest tests/test_dashboard_realtime.py

src/webrtc/static/**
src/webrtc/chat_real.html
  -> pytest tests/test_mesh_playwright.py
  -> pytest tests/test_webrtc_test_session_playwright.py
```

If tests are missing in a restored or partial repository, the selector records the missing paths and the runner marks verification as blocked instead of pretending checks passed.

### `test_runner.py`

Executes allowed commands and captures:

- command
- exit code
- stdout
- stderr
- start time
- duration

The runner uses timeouts and writes each result to `automation/artifacts/test-runs/<task_id>/`.

### `failure_analyzer.py`

Summarizes failing tests and asks whether the failure appears related to the current patch.

Allowed outcomes:

```text
repair
  The failure is related and likely fixable in allowed paths.

blocked
  The failure needs files, commands, or context outside policy.

unrelated
  The failure is pre-existing or environment-related.
```

Only `repair` may trigger another developer loop.

### `reviewer.py`

Performs a final self-review before reporting success.

Review checklist:

- Does the diff satisfy every acceptance item?
- Were all required checks run or explicitly blocked?
- Did the task touch only allowed paths?
- Are there generated files that should not be included?
- Does the report contain enough evidence for a human reviewer?

### `artifact_store.py`

Writes all durable outputs:

- plan JSON
- applied patch
- final diff
- command logs
- model transcripts
- task report
- morning summary

The artifact store owns `automation/artifacts/**` writes so model-generated code cannot silently alter audit records.

## State Machine

```text
ready
  -> policy_rejected
  -> running

running
  -> planned
  -> patched
  -> testing
  -> repairing
  -> passed
  -> blocked
  -> failed

passed
  -> done

blocked
  -> failed

failed
  -> failed archive
```

## Success Criteria

A task is marked `done` only when:

- the final patch applies cleanly
- all modified files are allowed
- no forbidden paths are touched
- every acceptance item is checked in the report
- every `required_check` passed
- optional checks either passed or have an explicit skip reason
- a final report and patch artifact exist

If required checks cannot run because the repository is partial, missing dependencies, or missing tests, the task is marked `blocked`, not `done`.

## Error Handling

### Invalid Task

The task moves to `failed/` with a policy report. No model call is made.

### Model Output Is Not Valid JSON

The runner asks for one structured retry. If the retry fails, the task is blocked.

### Patch Does Not Apply

The runner asks for one patch regeneration using the apply error. If the second patch fails, the task is blocked.

### Test Fails

The runner invokes `failure_analyzer.py`. Related failures enter the repair loop. Unrelated or out-of-policy failures block the task.

### Repair Limit Reached

The task is marked `failed` with the latest patch, logs, and failure analysis preserved.

## Testing Strategy

The agent itself should be tested without requiring a live model by using a stub model backend.

Unit tests:

- task contract validation
- policy path matching
- command prefix allowlist
- diff validation
- test selection mapping
- artifact writing
- state transitions

Integration tests:

- valid low-risk task completes with stub patch and passing command
- forbidden path patch is rejected
- failing test triggers one repair attempt
- missing test command marks task blocked
- medium-risk task stops before patch application
- high-risk task produces plan only

The first implementation should avoid Playwright. The runner can later manage Playwright checks as task-required commands after the backend loop is stable.

## MVP Scope

The first shippable version should include:

1. JSON task loading.
2. Static policy loading.
3. Patch-only and worktree modes.
4. Stub model backend.
5. Plan JSON validation.
6. Unified diff validation and application.
7. Required check execution through a command allowlist.
8. One bounded repair loop.
9. Final patch, test logs, transcript, and report.

The MVP does not need provider-specific model quality work. It only needs the model gateway interface plus `stub` mode, because the closed-loop mechanics are the first risk to validate.

## Human Review Flow

After each task:

```text
automation/artifacts/reports/<task_id>.md
automation/artifacts/patches/<task_id>.patch
automation/artifacts/test-runs/<task_id>/*.json
automation/artifacts/transcripts/<task_id>/*.json
```

The human reviewer reads the report and applies or rejects the patch. Merge remains a human-controlled action.

## Open Decisions

The implementation plan should choose concrete defaults for:

- whether `.automation/worktrees/` or `/tmp/rtc-training-agent-worktrees/` is better for local worktrees
- whether task files should be moved or copied between `ready`, `running`, `done`, and `failed`
- whether command allowlists match exact full commands or prefix arrays
- whether medium-risk tasks require an interactive approval prompt or simply stop with a report

For the first version, prefer the simpler option in each case:

- worktrees under `.automation/worktrees/`
- move task files between state directories
- prefix-array command allowlists
- medium-risk tasks stop with a report

