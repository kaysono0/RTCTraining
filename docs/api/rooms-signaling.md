# Rooms And Signaling API

All JSON success responses use:

```json
{"ok": true, "data": {}}
```

All JSON error responses use the shared error envelope documented in
`docs/api/errors.md`.

## Rooms

### POST /rooms/join

Joins a room or refreshes an existing peer in the room.

Required JSON fields:

- `room_id`
- `client_id`
- `display_name`

Response data:

- `room_id`
- `peer_id`
- `existing_peers`: peers already present in the room.

Errors:

- `bad_request` when a required field is missing.
- `room_full` when the room already reached the member limit.

### POST /rooms/leave

Leaves a room.

Required JSON fields:

- `room_id`
- `client_id`

Response data:

- `room_id`
- `peer_id`
- `left`: whether a peer was removed.

### GET /rooms/{roomId}/members

Returns members for one room.

Response data:

- `room_id`
- `members`: peer id and display name pairs.

### GET /rooms/members

Returns the in-memory room snapshot.

Response data:

- `rooms`: room ids mapped to members and pending message counts.

## Signaling

RTCTraining uses simple HTTP polling signaling for local experiments. Signaling
messages are transient in-memory messages.

### POST /signal

Queues a signaling message for another peer.

Required JSON fields:

- `room_id`
- `from_peer_id`
- `to_peer_id`
- `type`: one of `offer`, `answer`, `candidate`, `renegotiate`.
- `payload`: signaling payload object.

Response data:

- The queued signaling message.

Errors:

- `bad_request` when a required field is missing or `type` is unsupported.
- `not_found` when either peer is not present in the room.

### GET /signal/pending

Returns and clears pending messages for a peer.

Query:

- `room_id` required.
- `client_id` required.

Response data:

- `messages`: pending signaling messages.

## Dashboard Snapshot

### GET /dashboard/snapshot

Builds a room-scoped Dashboard snapshot from room and stats state.

Query:

- `room_id` required.

Response data:

- `room_id`
- `members`
- `peer_pairs`
- latest stats values and available test-session metadata when present.

## Test Session Follow-Up Endpoints

The test session start, finish, and CSV export behavior is documented in
`docs/api/stats.md`.

### POST /stats/test/cancel

Cancels a running test session.

Required JSON fields:

- `test_session_id`

Response data:

- `session`: canceled session.

Errors:

- `bad_request` when `test_session_id` is missing.
- `not_found` when the session does not exist.

### GET /stats/test/sessions

Lists finished test sessions.

Query:

- `room_id` optional.

Response data:

- `sessions`: finished sessions, optionally filtered by room.

### GET /stats/test/download/{file_path}

Downloads a generated CSV file. `file_path` must resolve inside the configured
test session export directory.

Response:

- CSV file response with `Content-Disposition: attachment`.

Errors:

- `not_found` when the file does not exist or the path is outside the export
  directory.
