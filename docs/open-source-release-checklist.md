# Open Source Release Checklist

Use this checklist before publishing RTCTraining.

## Repository Metadata

- [ ] Repository description explains that RTCTraining is a Local/LAN WebRTC
  experiment and diagnostics project.
- [ ] Topics include `webrtc`, `getstats`, `rtc`, `dashboard`, `csv`, and
  `playwright`.
- [ ] `README.md` is the primary public entry point.
- [ ] `LICENSE` is present and matches the intended license.
- [ ] `SECURITY.md`, `CONTRIBUTING.md`, issue templates, PR template, and
  Dependabot config are present.

开源者需要提供以下信息与材料：

- Final license choice and copyright holder name.
- Security contact email or private disclosure preference.
- Repository description and topic list.
- Public maintainer name or organization name.

## Product Material

- [ ] WebRTC experiment page screenshot.
- [ ] Dashboard live metrics screenshot.
- [ ] Dashboard CSV comparison screenshot.
- [ ] Short demo video or GIF.
- [ ] Optional sample CSV files that do not contain private local paths or
  personal data.

开源者需要提供以下信息与材料：

- Screenshot files for README.
- Demo video or GIF.
- Optional sample CSV files for docs or examples.

## Documentation

- [ ] Quickstart works on a clean machine.
- [ ] LAN certificate instructions are accurate.
- [ ] `docs/architecture.md` reflects current service boundaries.
- [ ] `docs/api/stats.md` documents stats and test session behavior.
- [ ] `docs/api/rooms-signaling.md` documents rooms, signaling, snapshot, and
  session follow-up endpoints.
- [ ] `docs/api/dashboard.md` documents Dashboard proxy safety.
- [ ] `docs/api/csv_schema.md` documents every exported CSV field.
- [ ] Historical plans and internal notes live under `docs/internal/`.

## Verification

Run:

```bash
make test-unit
make harness-smoke
make test-e2e
make test
git diff --check
```

For CI, `make test-unit` and `make harness-smoke` should pass in GitHub Actions.
Playwright E2E remains a local/manual gate until browser install cost and
self-signed HTTPS behavior are acceptable for required PR checks.

## Release

- [ ] Move `CHANGELOG.md` entries from `Unreleased` to the release version.
- [ ] Tag the first release, for example `v0.1.0`.
- [ ] Include known limits: desktop Chrome focus, local/LAN scope, no auth, no
  TURN/SFU/MCU, no production deployment support.
- [ ] Confirm generated artifacts are not tracked: `certs/`, `data/`, `.venv/`,
  `.pytest_cache/`.
