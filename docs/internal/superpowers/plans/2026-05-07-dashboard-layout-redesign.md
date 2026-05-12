# Dashboard Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Dashboard workstation layout while preserving the existing API, DOM IDs, and test hooks.

**Architecture:** The change is frontend-only. `templates/dashboard/index.html` defines the new section hierarchy, `static/dashboard/dashboard.css` controls desktop and mobile layout, and `static/dashboard/dashboard.js` only updates the optional NACK summary element.

**Tech Stack:** Native HTML, CSS, JavaScript, pytest, Playwright.

---

### Task 1: HTML Layout Contract

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `templates/dashboard/index.html`

- [ ] **Step 1: Write the failing test**

Add assertions to `test_dashboard_homepage_declares_complete_stats_surface`:

```python
    for class_name in [
        "dashboard-control-bar",
        "dashboard-summary-strip",
        "dashboard-main-grid",
        "dashboard-side-column",
        "dashboard-latest-column",
        "dashboard-history-section",
        "dashboard-table-scroll",
    ]:
        assert f'class="{class_name}"' in body
    assert 'id="nackSummary"' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_dashboard_homepage_declares_complete_stats_surface -v
```

Expected: FAIL because the new layout classes and `#nackSummary` do not exist.

- [ ] **Step 3: Implement minimal HTML structure**

Restructure `templates/dashboard/index.html` so it has:

```html
<section class="dashboard-control-bar">...</section>
<section class="dashboard-summary-strip">...</section>
<section class="dashboard-main-grid">...</section>
<section class="dashboard-history-section">...</section>
```

Keep all current IDs intact.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_dashboard_homepage_declares_complete_stats_surface -v
```

Expected: PASS.

### Task 2: Responsive Layout Behavior

**Files:**
- Modify: `tests/test_playwright_e2e.py`
- Modify: `static/dashboard/dashboard.css`

- [ ] **Step 1: Write the failing Playwright test**

Add a Dashboard mobile layout test:

```python
def test_dashboard_workstation_layout_fits_mobile_viewport(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    page.set_viewport_size({"width": 390, "height": 844})

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")

    for selector in [
        ".dashboard-control-bar",
        ".dashboard-summary-strip",
        ".dashboard-latest-column",
        ".dashboard-side-column",
        ".dashboard-history-section",
    ]:
        expect(page.locator(selector)).to_be_visible()

    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.locator(".dashboard-table-scroll").evaluate(
        "element => element.scrollWidth > element.clientWidth"
    )
    assert page.locator("#checkServiceButton").bounding_box()["width"] >= 340
    assert page.locator("#clearStatsButton").bounding_box()["width"] >= 340
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_workstation_layout_fits_mobile_viewport -v
```

Expected: FAIL because the layout classes and responsive rules do not exist yet.

- [ ] **Step 3: Implement responsive CSS**

Update `static/dashboard/dashboard.css`:

- `.dashboard-control-bar` uses a desktop grid and mobile single column.
- `.dashboard-summary-strip` uses desktop multi-column cards and mobile two columns.
- `.dashboard-main-grid` uses `minmax(280px, 0.35fr) minmax(0, 0.65fr)`.
- `.dashboard-history-section` spans full width.
- `.dashboard-table-scroll` owns horizontal table scrolling.
- `#statsHistoryTable thead th` is sticky.
- At `max-width: 760px`, page-level horizontal overflow is hidden while the table container scrolls.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_workstation_layout_fits_mobile_viewport -v
```

Expected: PASS.

### Task 3: NACK Summary Rendering

**Files:**
- Modify: `tests/test_playwright_e2e.py`
- Modify: `static/dashboard/dashboard.js`

- [ ] **Step 1: Write the failing test**

Extend `test_dashboard_renders_nack_analysis_fields`:

```python
    expect(page.locator("#nackSummary")).to_have_text("NACK: disabled / 0")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_renders_nack_analysis_fields -v
```

Expected: FAIL because the JavaScript does not update `#nackSummary`.

- [ ] **Step 3: Implement NACK summary update**

In `renderLatestStats`, after selecting `latest`, update `#nackSummary`.

Expected value format:

```text
NACK: <nack_mode> / <nack_count>
```

If no latest sample exists, render:

```text
NACK: -
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_renders_nack_analysis_fields -v
```

Expected: PASS.

### Task 4: Final Verification and Commit

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

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add templates/dashboard/index.html static/dashboard/dashboard.css static/dashboard/dashboard.js tests/test_ui_routes.py tests/test_playwright_e2e.py
git commit -m "Redesign dashboard layout"
```

Expected: commit contains only Dashboard redesign implementation files.

