# Dashboard API

The Dashboard page only calls Dashboard Service.

Dashboard Service may proxy requests to WebRTC Service when the requested `origin` passes the origin allowlist.

Dashboard Service is not a general-purpose HTTP proxy.

## Safety Boundary

- Default Dashboard binding is `127.0.0.1:8081`.
- Dashboard proxy requests must stay scoped to local trusted WebRTC origins.
- The origin allowlist accepts full origins such as `https://localhost:8080` and host entries such as `localhost`.
- Invalid or unallowed origins must return the standard error envelope.
- The Dashboard page must degrade gracefully when WebRTC Service is unreachable.

## Endpoints

| Method | Path | Upstream |
| --- | --- | --- |
| `GET` | `/api/webrtc/members` | `/rooms/members` |
| `GET` | `/api/webrtc/stats` | `/stats` |
| `GET` | `/api/webrtc/stats/history` | `/stats/history` |
| `GET` | `/api/webrtc/stats/peers` | `/stats/peers` |
| `GET` | `/api/webrtc/dashboard/snapshot` | `/dashboard/snapshot` |
| `POST` | `/api/webrtc/clear_stats` | `/clear_stats` |
| `GET` | `/api/webrtc/stats/test/sessions` | `/stats/test/sessions` |
| `GET` | `/api/webrtc/stats/test/download/{file_path}` | `/stats/test/download/{file_path}` |

## Origin Query

Dashboard proxy endpoints accept:

- `origin`: WebRTC Service origin. Defaults to `https://localhost:8080`.

The default allowlist is:

```text
localhost,127.0.0.1,::1
```

Example:

```text
/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1
```
