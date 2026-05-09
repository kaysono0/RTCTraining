# API Errors

All JSON error responses use:

```json
{"ok": false, "error": {"code": "...", "message": "...", "details": {}}}
```

## Common Error Codes

| Code | HTTP | Meaning |
| --- | --- | --- |
| `bad_request` | 400 | Missing or invalid request field |
| `not_found` | 404 | Requested peer, room, file, or test session does not exist |
| `room_full` | 409 | Room reached configured member limit |
| `service_unreachable` | 502 | Dashboard cannot reach WebRTC Service |
| `upstream_error` | 502 | WebRTC Service returned an error to Dashboard Service |
| `upstream_non_json` | 502 | WebRTC Service returned a non-JSON response |

## Rules

- HTTP handlers map domain errors to stable `code` strings.
- `details` must be an object.
- Public clients should use `code` for branching and `message` for display.
