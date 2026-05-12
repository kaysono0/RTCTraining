# RTCTraining

RTCTraining is a Local/LAN WebRTC learning and experiment project.

It runs a local WebRTC service, a local Dashboard service, collects browser
`getStats()` samples, and exports CSV data for repeatable RTC experiments.

## What It Does

- Runs a local browser WebRTC experiment page.
- Connects peers through local HTTP polling signaling.
- Collects browser `getStats()` samples.
- Shows live room, peer pair, and metric state in Dashboard.
- Exports experiment sessions as CSV files.
- Compares multiple CSV files for NACK, ABR, bitrate, loss, jitter, FPS, and RTT.
- Provides a lightweight smoke harness for service startup and API checks.

RTCTraining is designed for trusted local development networks. It is not a
production chat system and does not include accounts, authentication, TURN, SFU,
MCU, recording, or long-term storage.

## Requirements

- Python 3.12 recommended.
- Desktop Chrome for browser experiments.
- Local camera and microphone permission, or Playwright fake media for E2E.
- A trusted local or LAN network.

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

## Run Locally

Start each service in a separate terminal:

```bash
make run-webrtc
```

```bash
make run-dashboard
```

Open:

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

The WebRTC page uses a self-signed local certificate. Browser certificate
warnings are expected for local development.

## Run An Experiment

1. Open the WebRTC page in two or three desktop Chrome tabs or machines.
2. Use the same room id and different display names.
3. Join the room from each page.
4. Choose experiment controls such as NACK, ABR, or manual bitrate before the
   session starts.
5. Click `Start Session`.
6. Watch live peer-pair metrics in Dashboard.
7. Finish the session and download CSV files.
8. Load multiple CSV files in Dashboard to compare runs.

## Screenshots And Video

开源者需要提供以下信息与材料：

- WebRTC experiment page screenshot.
- Dashboard live metrics screenshot.
- Dashboard CSV comparison screenshot.
- Short demo video or GIF showing join, stats, session finish, and CSV compare.
- Preferred project tagline for the repository description.

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

## Documentation

- Architecture: `docs/architecture.md`
- Stats API: `docs/api/stats.md`
- Rooms and signaling API: `docs/api/rooms-signaling.md`
- Dashboard API: `docs/api/dashboard.md`
- Error envelope: `docs/api/errors.md`
- CSV schema: `docs/api/csv_schema.md`
- Verification: `docs/agents/verification.md`
- Open source release checklist: `docs/open-source-release-checklist.md`
- Internal history and plans: `docs/internal/`

## Common Issues

### Browser Warns About The Certificate

Run `make cert`, then open `https://localhost:8080` and allow the local
self-signed certificate in the browser.

### LAN Device Cannot Open The WebRTC Page

Generate a certificate that includes the LAN IP:

```bash
.venv/bin/python scripts/generate_cert.py --host 192.168.x.x
```

Then run:

```bash
make urls
```

### Dashboard Cannot Reach WebRTC Service

Check that the requested WebRTC origin is in
`RTC_DASHBOARD_ORIGIN_ALLOWLIST`. Dashboard proxy allowlist entries are exact
origins such as `https://localhost:8080`.

### Playwright E2E Fails On A Fresh Machine

Install the browser dependency once:

```bash
.venv/bin/python -m playwright install chromium
```

## Contributing

Read `CONTRIBUTING.md` before opening a pull request.

## Security

Read `SECURITY.md` before exposing RTCTraining outside a trusted local network.

## License

RTCTraining is released under the MIT License. See `LICENSE`.
