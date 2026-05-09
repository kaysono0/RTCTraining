# Security

Do not expose RTCTraining directly to the public internet.

RTCTraining is a Local/LAN experiment project. It has no authentication and is designed for trusted development networks.

The Dashboard proxy must be restricted by an origin allowlist and must not become a general-purpose HTTP proxy.

Generated certificates and runtime data are local development artifacts and should not be committed.
