# Simplified ABR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable simplified ABR that only adjusts video sender `maxBitrate`.

**Architecture:** Extend `static/webrtc/chat_real_bitrate.js` to own both manual and ABR bitrate control. The ABR decision function is deterministic and testable through Playwright hooks. Stats reads shared state and records ABR fields.

**Tech Stack:** Native HTML/CSS/JavaScript, WebRTC sender parameters, pytest, Playwright.

---

### Task 1: Page Contract

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `templates/webrtc/chat_real.html`

- [ ] Add assertions for `abrModeSelect`, `abrMinBitrateInput`, `abrMaxBitrateInput`, `abrStepKbpsInput`, `abrLossThresholdInput`, `abrRttThresholdInput`, and `abrModeState`.
- [ ] Run `tests/test_ui_routes.py::test_webrtc_homepage_loads_experiment_shell` and verify failure.
- [ ] Add the ABR controls to `room-controls`.
- [ ] Run the same test and verify pass.

### Task 2: ABR State and Hooks

**Files:**
- Modify: `tests/test_playwright_e2e.py`
- Modify: `static/webrtc/chat_real_shared.js`
- Modify: `static/webrtc/chat_real_bootstrap.js`
- Modify: `static/webrtc/chat_real_bitrate.js`

- [ ] Add a Playwright test for `setAbrMode("on")`, `runAbrDecision()`, target bitrate, and decision label.
- [ ] Run the test and verify failure.
- [ ] Add shared ABR state and test hooks.
- [ ] Implement `setAbrMode`, `runAbrDecision`, and rendering.
- [ ] Run the test and verify pass.

### Task 3: Sender Application

**Files:**
- Modify: `tests/test_playwright_e2e.py`
- Modify: `static/webrtc/chat_real_bitrate.js`

- [ ] Extend the ABR Playwright test to verify decrease and increase decisions update `senderMaxBitrateBps`.
- [ ] Run the test and verify failure.
- [ ] Reuse existing sender application path so ABR updates call `applyCurrentBitrate()`.
- [ ] Run the test and verify pass.

### Task 4: Stats Fields

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/webrtc/chat_real_stats.js`

- [ ] Add a route test verifying stats records `abr_mode`, `abr_target_bitrate_bps`, and `abr_decision`.
- [ ] Run the test and verify failure.
- [ ] Add the fields to stats metrics.
- [ ] Run the test and verify pass.

### Task 5: Verification and Commit

**Files:**
- Verify all touched files.

- [ ] Run `.venv/bin/python -m pytest tests/test_ui_routes.py tests/test_playwright_e2e.py -v`.
- [ ] Run `make test-e2e`.
- [ ] Commit with `git commit -m "Add simplified ABR controls"`.

