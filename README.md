# RTCTraining

RTCTraining is a Local/LAN WebRTC learning and experiment project.

It runs a local WebRTC service, a local Dashboard service, collects browser
`getStats()` samples, and exports CSV data for repeatable RTC experiments.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make cert
make harness-smoke
```

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

It does not replace unit tests or Playwright E2E tests.

## Testing

```bash
make test-unit
make test-e2e
make test
```
