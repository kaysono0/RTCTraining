# RTCTraining

RTCTraining is a Local/LAN WebRTC learning and experiment project.

It runs a local WebRTC service, a local Dashboard service, collects browser
`getStats()` samples, and exports CSV data for repeatable RTC experiments.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
make cert
make harness-smoke
```

The app reads `RTC_*` environment variables directly from the shell. The `.env`
file is a reference for local configuration; load it with your shell or tooling
when you want to override defaults.

For manual browser testing, start each service in a separate terminal:

```bash
make run-webrtc
```

```bash
make run-dashboard
```

Open:

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

## Local Harness

Run a lightweight service-level smoke check:

```bash
make harness-smoke
```

The harness starts WebRTC Service and Dashboard Service, checks both pages,
verifies JSON API envelopes, checks Dashboard proxy access, verifies CSV export
headers, and shuts the services down.

By default it uses ephemeral local ports to avoid collisions with manually
running services. Pass `--webrtc-port` and `--dashboard-port` to
`automation.harness.smoke` when fixed ports are needed.

It does not replace unit tests or Playwright E2E tests.

## Testing

```bash
make test-unit
make harness-smoke
make test-e2e
make test
```

## Architecture And API

- Architecture: `docs/architecture.md`
- Stats API: `docs/api/stats.md`
- Dashboard API: `docs/api/dashboard.md`
- Error envelope: `docs/api/errors.md`
- CSV schema: `docs/api/csv_schema.md`

## Contributing

Read `CONTRIBUTING.md` before opening a pull request.

## Security

Read `SECURITY.md` before exposing RTCTraining outside a trusted local network.
