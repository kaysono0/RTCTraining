# Test Session Lifecycle

## Scope

Add the first test session slice for the WebRTC experiment page.

This slice includes:

- Start, finish, and cancel lifecycle.
- Session metadata, preset, and weak network condition fields.
- Stats payload association through `test_session_id`.
- Sample counting on finish by querying existing `StatsStore`.

This slice does not generate downloadable CSV files. CSV file generation is the next phase.

## Backend

Add a pure Python `TestSessionStore`.

Routes:

- `POST /stats/test/start`
- `POST /stats/test/finish`
- `POST /stats/test/cancel`

Start requires:

- `room_id`
- `peer_id`

Optional fields:

- `preset`
- `metadata`
- `weak_network`

Finish computes `sample_count` from existing stats filtered by:

- `room_id`
- `peer_id`
- `test_session_id`

## Frontend

The WebRTC page adds a test session panel with:

- `#testPresetSelect`
- `#testWeakNetworkInput`
- `#testSessionNoteInput`
- `#startTestSessionButton`
- `#finishTestSessionButton`
- `#cancelTestSessionButton`
- `#testSessionState`

The stats uploader sends:

```js
test_session_id: shared.state.testSessionId
```

## Test Hooks

Expose:

- `startTestSession(options)`
- `finishTestSession()`
- `cancelTestSession()`
- `getTestSessionId()`
- `getTestSessionStatus()`
