# Manual Sender Bitrate Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manual video sender bitrate control and expose the configured bitrate in stats.

**Architecture:** Add a focused `static/webrtc/chat_real_bitrate.js` module that owns bitrate state rendering and sender parameter updates. Existing session code calls into that module when peer connections are created. Existing stats code reads shared state and records bitrate config fields in each sample.

**Tech Stack:** Native HTML, CSS, JavaScript, WebRTC `RTCRtpSender.setParameters`, pytest, Playwright.

---

### Task 1: Page Contract

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `templates/webrtc/chat_real.html`

- [ ] **Step 1: Write failing HTML contract assertions**

Add to `test_webrtc_homepage_loads_experiment_shell`:

```python
    assert 'id="senderBitrateInput"' in body
    assert 'id="applyBitrateButton"' in body
    assert 'id="bitrateModeState"' in body
    assert "chat_real_bitrate.js" in body
```

- [ ] **Step 2: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_homepage_loads_experiment_shell -v
```

Expected: FAIL because the controls and script are absent.

- [ ] **Step 3: Implement HTML controls**

Add a `Bitrate` numeric input, `Apply` button, and `bitrate_auto` state label to the existing `room-controls` area. Add the new script before `chat_real_session.js`.

- [ ] **Step 4: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_homepage_loads_experiment_shell -v
```

Expected: PASS.

### Task 2: Manual Bitrate Module

**Files:**
- Modify: `tests/test_ui_routes.py`
- Create: `static/webrtc/chat_real_bitrate.js`
- Modify: `static/webrtc/chat_real_shared.js`
- Modify: `static/webrtc/chat_real_bootstrap.js`

- [ ] **Step 1: Write static asset assertions**

Extend `test_webrtc_static_asset_loads` with:

```python
("chat_real_bitrate.js", "RTCTrainingBitrate")
```

Add a test that verifies the JS contains:

```python
assert "setParameters" in body
assert "sender_max_bitrate_bps" not in body
```

- [ ] **Step 2: Run the tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_static_asset_loads tests/test_ui_routes.py::test_webrtc_bitrate_module_sets_sender_parameters -v
```

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement module and bootstrap wiring**

Create `RTCTrainingBitrate` with:

```javascript
setSenderBitrateKbps(value)
applyCurrentBitrate()
applyBitrateToPeerConnection(peerConnection)
renderBitrateMode()
```

Update shared state with `bitrateMode` and `senderMaxBitrateBps`.

Update bootstrap to wire `#applyBitrateButton` and expose hooks.

- [ ] **Step 4: Run the tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_static_asset_loads tests/test_ui_routes.py::test_webrtc_bitrate_module_sets_sender_parameters -v
```

Expected: PASS.

### Task 3: Runtime Behavior

**Files:**
- Modify: `tests/test_playwright_e2e.py`
- Modify: `static/webrtc/chat_real_session.js`

- [ ] **Step 1: Write Playwright behavior test**

Add a test that:

- Opens the WebRTC page.
- Uses test hooks to set `800`.
- Verifies mode is `manual`.
- Verifies sender cap is `800000`.
- Sets `0`.
- Verifies mode returns to `auto`.

- [ ] **Step 2: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_webrtc_page_applies_manual_sender_bitrate -v
```

Expected: FAIL before implementation.

- [ ] **Step 3: Apply bitrate on peer connection creation**

In `ensurePeerConnection`, after local tracks are added, call:

```javascript
window.RTCTrainingBitrate.applyBitrateToPeerConnection(peerConnection)
```

Only call it when the module exists.

- [ ] **Step 4: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_webrtc_page_applies_manual_sender_bitrate -v
```

Expected: PASS.

### Task 4: Stats Fields

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/webrtc/chat_real_stats.js`

- [ ] **Step 1: Write stats field assertions**

Add a test that verifies `chat_real_stats.js` records:

```javascript
bitrate_mode: shared.state.bitrateMode
sender_max_bitrate_bps: shared.state.senderMaxBitrateBps
```

- [ ] **Step 2: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_stats_uploader_records_sender_bitrate_config -v
```

Expected: FAIL before implementation.

- [ ] **Step 3: Add stats fields**

Add the two metrics to each collected peer stats sample.

- [ ] **Step 4: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_webrtc_stats_uploader_records_sender_bitrate_config -v
```

Expected: PASS.

### Task 5: Verification and Commit

**Files:**
- Verify all files touched by this plan.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py tests/test_playwright_e2e.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run E2E suite**

Run:

```bash
make test-e2e
```

Expected: all E2E tests pass.

- [ ] **Step 3: Commit**

Run:

```bash
git add templates/webrtc/chat_real.html static/webrtc/chat_real.css static/webrtc/chat_real_shared.js static/webrtc/chat_real_bitrate.js static/webrtc/chat_real_bootstrap.js static/webrtc/chat_real_session.js static/webrtc/chat_real_stats.js tests/test_ui_routes.py tests/test_playwright_e2e.py
git commit -m "Add manual sender bitrate control"
```

Expected: commit contains only manual bitrate implementation files.

