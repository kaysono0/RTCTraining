# Contributing

## Development Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make cert
make harness-smoke
```

## Test Commands

```bash
make test-unit
make harness-smoke
make test-e2e
make test
```

## Pull Request Expectations

- Keep WebRTC Service and Dashboard Service boundaries clear.
- Keep stores independent from aiohttp.
- Preserve JSON response envelopes.
- Preserve window.__RTCTrainingTestHooks.
- Add or update tests before changing behavior.
- Update documentation when public API, CSV schema, startup behavior, or harness behavior changes.
- Update CHANGELOG.md for user-visible behavior, command, CI, or schema changes.
