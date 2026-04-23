# Codex Context Transfer Contract Design

## Goal

Define the canonical input contract used by RTCTraining's autonomous development bridge when it prepares context for `plan`, `develop`, and `repair` phases.

The contract must make every phase explicit, bounded, and replayable. A fresh `codex exec` process should be able to reconstruct the task from the task contract, the current plan, the baseline manifest, the failure summary, and a small set of phase-specific fields.

## Source Context

This design builds on the current RTCTraining automation runner:

- `automation/runner/codex_bridge.py` already sends task JSON to `codex exec`, records transcript chunks, and exports unified diffs.
- `automation/runner/model_gateway.py` already exposes `plan`, `develop`, and `repair` entry points.
- `automation/runner/task_loader.py` already validates task contracts, including `context_files`, `allowed_paths`, `required_checks`, and optional `baseline`.
- `automation/runner/task_baseline.py` already computes and validates the baseline manifest used before a task runs.
- `automation/artifacts/transcripts/<task_id>.jsonl` already stores runtime evidence for each run.

The missing piece is a stable, explicit contract that says which fields each phase must receive and how those fields should be rendered for Codex.

## Non-Goals

- No change to the overall task lifecycle.
- No long-lived Codex session or process reuse.
- No new provider SDK integration.
- No automatic widening of task authority.
- No attempt to infer missing fields from prior process memory.

## Recommended Approach

Use a single canonical envelope with a `phase` discriminator and phase-specific required fields.

The envelope is rendered by `codex_bridge` into a prompt that is deterministic, structured, and easy to inspect. The bridge also writes a compact input summary to transcript so that each run can be replayed without relying on process memory.

This is better than separate ad hoc prompts because it keeps the runtime contract and the documentation aligned. It is also better than a minimal free-form prompt because the runner can validate required inputs before calling Codex.

## Canonical Envelope

Every request to the bridge must include:

- `phase`: one of `plan`, `develop`, or `repair`
- `task`: the normalized task contract
- `plan`: the current plan object, or `{}` for plan generation
- `failed_checks`: only for repair requests
- `repair_attempt`: only for repair requests

The `task` object is the authority source. It remains the same across phases and must include at least:

- `id`
- `title`
- `goal`
- `context_files`
- `allowed_paths`
- `forbidden_paths`
- `acceptance`
- `required_checks`
- `risk_level`
- `mode`
- `baseline`

## Phase Templates

### Plan

Purpose:

- Turn the task contract into a concrete execution plan.
- Identify the files that are expected to change.
- Identify the checks that are expected to run.

Required inputs:

- `task`
- `task.baseline`
- `task.context_files`
- `task.allowed_paths`
- `task.acceptance`

Prompt shape:

- State the phase explicitly as `plan`.
- Present the task goal.
- Present the baseline summary.
- Present context files and allowed paths.
- Ask for a concise plan object only.

Expected output:

- A structured plan summary.
- A list of files to inspect or change.
- A list of checks to run.

### Develop

Purpose:

- Make the repository change described by the accepted plan.
- Keep the patch bounded to the task's allowed scope.

Required inputs:

- `task`
- `plan`
- `task.baseline`
- `task.context_files`
- `task.allowed_paths`
- `task.acceptance`
- `task.required_checks`

Prompt shape:

- State the phase explicitly as `develop`.
- Present the task goal.
- Present the accepted plan.
- Present the baseline summary.
- Present the acceptance criteria and required checks.
- Instruct Codex to modify files directly and let the wrapper export the diff.

Expected output:

- A unified diff that changes only the task-authorized files.

### Repair

Purpose:

- Fix a failed develop attempt or a failed required check.
- Use the previous failure evidence instead of re-deriving it from process memory.

Required inputs:

- `task`
- `plan`
- `task.baseline`
- `task.context_files`
- `task.allowed_paths`
- `task.acceptance`
- `task.required_checks`
- `failed_checks`
- `repair_attempt`

Prompt shape:

- State the phase explicitly as `repair`.
- Present the task goal and accepted plan.
- Present the failure summary in machine-readable form.
- Present the required checks that failed.
- Instruct Codex to make the minimum patch needed to address the failure.

Expected output:

- A unified diff that resolves the specific failure and stays within task scope.

## Transcript Requirements

Each Codex run must write a compact input summary to `automation/artifacts/transcripts/<task_id>.jsonl` with enough detail to answer:

- Which phase ran?
- Which task ran?
- Which paths were in scope?
- Which checks were expected?
- Was this a repair attempt?
- What failure evidence was supplied?

The transcript does not need to repeat the full task JSON, but it must be sufficient to reconstruct the phase contract later.

## Success Criteria

The implementation is complete when all of the following are true:

- The bridge has one canonical request shape with phase-specific fields.
- `plan`, `develop`, and `repair` are documented as distinct input templates.
- The bridge records phase-aware input summaries in transcript.
- The runtime still accepts valid tasks and returns unified diffs for develop and repair.
- Tests verify the phase-specific prompt shape and the transcript summary fields.

