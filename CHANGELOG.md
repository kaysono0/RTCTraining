# Changelog

## Unreleased

- Added a lightweight local harness smoke command with `make harness-smoke`.
- Added `automation.harness` helpers for service process management and HTTP checks.
- Added harness tests to `make test-unit`.
- Added README quickstart and harness documentation.
- Added contributor and security entrypoint docs.
- Added a Phase 1 GitHub Actions workflow for unit tests.
- Added architecture, API, error envelope, and CSV schema documentation.
- Added environment-backed settings via `Settings.from_env()` and `.env.example`.
- Added Dashboard origin allowlist enforcement for proxied WebRTC requests.
- Added `StatsService` and `exports.stats_csv` boundaries while preserving the existing stats API.
- Added `TestSessionService` and removed local absolute file paths from test session CSV metadata.
- Added named WebRTC route registration via `src.webrtc.api.route_registry`.
- Added standalone Dashboard CSV parser and analysis browser modules.
- Added standalone Dashboard live stats presenter helpers for peer labels and newest sample selection.
- Added Dashboard core DOM/API client modules and a live stats view helper module.
- Added WebRTC stats normalizer and remote stats view browser modules.
- Added `DashboardSnapshotService` for Dashboard snapshot aggregation.
- Tightened Dashboard origin policy to exact origins instead of hostname wildcards.
- Added shared domain contracts for stats schema and public error codes.
- Added a Dashboard CSV view helper module.
- Added a Dashboard proxy client helper for upstream URL construction.
