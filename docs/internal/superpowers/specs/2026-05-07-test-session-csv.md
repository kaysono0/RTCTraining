# Test Session CSV

## Scope

Generate downloadable CSV files when a test session is finished.

The CSV files are generated from existing `StatsStore` samples. No second stats collection path is introduced.

## Isolation

Finish filters samples by:

- `room_id`
- `test_session_id`
- `peer_id`

Then it writes one CSV per `remote_peer_id`.

Each returned file entry includes:

- `room_id`
- `test_session_id`
- `peer_id`
- `remote_peer_id`
- `path`
- `download_url`

## Storage

Files are written under `Settings.test_sessions_dir` by default:

```text
data/test_sessions/<room_id>/<test_session_id>/<peer_id>/<remote_peer_id>.csv
```

Tests inject a temporary directory.

## Download

The WebRTC service exposes:

```text
GET /stats/test/download/{file_path}
```

The handler only serves files inside the configured test session directory.

## Frontend

After `finishTestSession()`, the WebRTC page renders links in:

```text
#testSessionDownloads
```
