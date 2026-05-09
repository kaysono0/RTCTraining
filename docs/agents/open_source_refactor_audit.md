# Open Source Refactor Audit

本文档记录 `feature/harness-smoke` 分支对开源架构重构计划的完成证据和剩余门禁。

## Objective

将 RTCTraining 从本地实验 Demo 形态重构为边界清晰、契约稳定、易读易扩展、带轻量验证 harness 的开源 WebRTC 实验平台。

## Evidence Checklist

| Requirement | Evidence |
| --- | --- |
| Agent guide under 200 lines with progressive disclosure | `AGENTS.md` is 199 lines and points to `docs/` for detail. |
| Written phased refactor plan | `docs/superpowers/plans/2026-05-09-open-source-architecture-refactor.md`. |
| Open-source entrypoints | `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.env.example`, `.github/workflows/ci.yml`. |
| API and architecture contracts | `docs/architecture.md`, `docs/api/stats.md`, `docs/api/dashboard.md`, `docs/api/errors.md`, `docs/api/csv_schema.md`. |
| Environment-backed settings | `src/webrtc/config.py`, covered by `tests/test_config.py`. |
| Dashboard origin allowlist | `src/dashboard/origin_policy.py`, exact-origin matching, covered by `tests/test_dashboard_origin_policy.py`. |
| Dashboard proxy client helper | `src/dashboard/proxy_client.py`, covered by `tests/test_dashboard_proxy_client.py`. |
| Backend service boundaries | `StatsService`, `TestSessionService`, `DashboardSnapshotService` under `src/webrtc/services/`. |
| Domain contracts | `src/webrtc/domain/stats_schema.py` and `src/webrtc/domain/errors.py`, covered by `tests/test_domain_contracts.py`. |
| Stable CSV export boundary | `src/webrtc/exports/stats_csv.py`, compatibility wrapper in `src/webrtc/csv_export.py`. |
| Named WebRTC route registry | `src/webrtc/api/route_registry.py`, covered by `tests/test_ui_routes.py`. |
| Dashboard frontend modules | `static/dashboard/core/`, `static/dashboard/csv/parser.js`, `static/dashboard/csv/analysis.js`, `static/dashboard/csv/view.js`, `static/dashboard/live/`. |
| WebRTC stats frontend modules | `static/webrtc/rtc/stats_normalizer.js`, `static/webrtc/ui/remote_stats_view.js`. |
| Lightweight harness | `automation/harness/`, `make harness-smoke`, covered by `tests/test_harness.py`. |
| ChangeLog updated | `CHANGELOG.md` has `Unreleased` entries for docs, CI, harness, settings, services, and frontend modules. |
| Unit verification | `make test-unit PYTHON=/Users/junsen/workspace/RTCTraining/.venv/bin/python` passed before exact-origin hardening with `163 passed in 2.62s`. After hardening, pure origin/config/docs checks pass; full unit rerun is blocked when the sandbox rejects aiohttp local port binding. |
| Workspace hygiene | `git status --short` clean; `git diff --check origin/main..HEAD` passed; no tracked `__pycache__`, `.pyc`, `certs/`, `data/`, `.pytest_cache/`, `.venv`. |

## Blocked Verification

The following gates are still required before this refactor can be considered complete:

```bash
make harness-smoke PYTHON=/Users/junsen/workspace/RTCTraining/.venv/bin/python
make test-e2e PYTHON=/Users/junsen/workspace/RTCTraining/.venv/bin/python
make test PYTHON=/Users/junsen/workspace/RTCTraining/.venv/bin/python
```

Current sandbox status:

- `make harness-smoke` fails because the sandbox rejects binding `127.0.0.1:8080` and `127.0.0.1:8081`.
- aiohttp handler tests can also fail in this sandbox when temporary `127.0.0.1` bind is rejected.
- `make test-e2e` requires local service ports and Chromium launch permissions.
- Escalated execution was rejected by the automatic approval reviewer due current Codex usage limit.

## Completion Rule

Do not mark the refactor complete until the blocked verification commands above pass in an environment that permits local port binding and Chromium execution.
