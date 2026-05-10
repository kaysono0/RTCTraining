# Stats API

All JSON success responses use:

```json
{"ok": true, "data": {}}
```

## Identity

Stats samples are isolated by:

- `room_id`
- `peer_id`
- `remote_peer_id`
- `test_session_id`

`test_session_id` may be absent for live ad hoc observations. Queries always require `room_id`.

## Core Metrics

| Field | Type | Unit | Nullable | Meaning |
| --- | --- | --- | --- | --- |
| `connection_state` | string | none | yes | `RTCPeerConnection.connectionState` |
| `ice_connection_state` | string | none | yes | `RTCPeerConnection.iceConnectionState` |
| `rtt_ms` | number | ms | yes | Selected candidate pair RTT |
| `packet_loss_rate` | number | percent | yes | Lost packets divided by expected inbound packets |
| `jitter_ms` | number | ms | yes | Inbound RTP jitter |
| `bitrate_kbps` | number | kbps | yes | Local bytes delta across samples |
| `fps` | number | frames/sec | yes | Browser-reported video frame rate |
| `codec` | string | none | yes | Browser codec MIME type |
| `nack_mode` | string | none | yes | Current NACK experiment mode |
| `bitrate_mode` | string | none | yes | Current manual bitrate mode |
| `abr_mode` | string | none | yes | Current simplified ABR mode |

## POST /stats

Uploads one normalized browser stats sample.

Required JSON fields:

- `room_id`
- `peer_id`
- `remote_peer_id`
- `metrics`

Optional JSON fields:

- `test_session_id`
- `timestamp`

Response data:

- `sample`: stored sample with `sample_index`.

## GET /stats

Returns latest samples for a room.

Query:

- `room_id` required
- `peer_id` optional
- `remote_peer_id` optional
- `test_session_id` optional

Response data:

- `samples`: latest matching samples.

## GET /stats/history

Returns historical samples for a room.

Query fields match `GET /stats`.

Response data:

- `samples`: ordered matching samples.

## GET /stats/peers

Returns observed peer pairs for a room.

Query:

- `room_id` required

Response data:

- `peers`: observed `peer_id -> remote_peer_id` pairs.

## GET /stats/export.csv

Exports room-scoped stats history as CSV.

Query fields match `GET /stats`.

CSV columns are documented in `docs/api/csv_schema.md`.

## POST /stats/test/start

Starts a test session. Required JSON fields:

- `room_id`
- `peer_id`

Optional JSON fields:

- `display_name`: human-readable local user name.
- `preset`: experiment preset, defaults to `manual`.
- `planned_duration_seconds`: planned recording length in seconds.
- `metadata`: free-form object for notes.
- `weak_network`: free-form object for network profile labels.

Response data:

- `session`: running session with `started_at`, `planned_duration_seconds`, and `duration_seconds: null`.

## POST /stats/test/finish

Finishes a test session and writes one CSV per `remote_peer_id`.

Required JSON fields:

- `test_session_id`

Response data:

- `session`: finished session with `duration_seconds`, `sample_count`, and `csv_files`.

Each `csv_files` item includes `filename`, `display_name`, `relative_path`, and `download_url`. Filenames are human-readable and include start time, local display name, peer pair, preset, NACK mode, ABR mode, bitrate, and actual duration.

## POST /clear_stats

Clears stats for a room.

Required JSON fields:

- `room_id`

Response data:

- `removed`: number of removed samples.
- `snapshot`: dashboard snapshot when available.
