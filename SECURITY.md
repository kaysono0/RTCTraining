# Security

Do not expose RTCTraining directly to the public internet.

RTCTraining is a Local/LAN experiment project. It has no authentication and is
designed for trusted development networks.

## Supported Versions

Security fixes are handled on the default branch until the project starts
publishing tagged releases.

## Reporting A Vulnerability

开源者需要提供以下信息与材料：

- Security contact email or private disclosure channel.
- Expected response time for security reports.
- Whether GitHub private vulnerability reporting should be enabled.

Until a disclosure channel is published, avoid sharing sensitive vulnerability
details in public issues.

## Security Boundary

- WebRTC Service defaults to `0.0.0.0:8080` for local and LAN experiments.
- Dashboard Service defaults to `127.0.0.1:8081`.
- Dashboard proxy requests must pass an exact-origin allowlist.
- Dashboard Service must not become a general-purpose HTTP proxy.
- Generated certificates and runtime data are local development artifacts.
- RTCTraining does not provide accounts, authentication, authorization, audit
  logging, rate limits, or production deployment hardening.

## Local Artifacts

Do not commit:

- `certs/`
- `data/`
- `.venv/`
- `.pytest_cache/`
- local agent or editor state
