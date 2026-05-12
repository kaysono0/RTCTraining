# Manual Sender Bitrate Control

## Goal

Add a manual sender bitrate control to the WebRTC experiment page. This is the first slice of Phase 4 and prepares the field model used by simplified ABR, test session metadata, and CSV comparison.

## Scope

This slice implements manual bitrate only.

Included:

- User input for video sender `maxBitrate`.
- Apply action that updates all existing video `RTCRtpSender` instances.
- Automatic application to future peer connections.
- Observable UI state.
- Test hooks for Playwright.
- Stats fields that record the current sender bitrate configuration.

Excluded:

- Simplified ABR decisions.
- Test session lifecycle.
- Finished-session CSV files.
- Dashboard multi-CSV comparison.

## UI

The WebRTC page adds a control in the existing `room-controls` area:

- `#senderBitrateInput`: numeric kbps input.
- `#applyBitrateButton`: applies the current value.
- `#bitrateModeState`: displays current state.

Initial state:

```text
bitrate_auto
```

After applying `800`:

```text
bitrate_manual_800kbps
```

The input accepts empty value, `0`, or positive integer:

- Empty or `0` clears the manual cap and returns to automatic mode.
- Positive integer sets `maxBitrate` to `kbps * 1000`.
- Negative or non-numeric values are rejected and shown as `bitrate_invalid`.

## Sender Behavior

The implementation uses the standard WebRTC sender parameters API:

```javascript
const parameters = sender.getParameters();
parameters.encodings = parameters.encodings && parameters.encodings.length
  ? parameters.encodings
  : [{}];
parameters.encodings[0].maxBitrate = targetBps;
await sender.setParameters(parameters);
```

When automatic mode is restored, `maxBitrate` is removed from the first encoding.

The applied bitrate must affect:

- Existing peer connections.
- New peer connections created after the setting changes.

Only video senders are modified.

## State

Shared frontend state adds:

```javascript
bitrateMode: "auto" | "manual",
senderMaxBitrateBps: null | number
```

## Stats

Every stats sample includes:

```javascript
bitrate_mode
sender_max_bitrate_bps
```

Manual mode records the configured bps value. Auto mode records `null`.

## Test Hooks

`window.__RTCTrainingTestHooks` adds:

```javascript
setSenderBitrateKbps(value)
getBitrateMode()
getSenderMaxBitrateBps()
```

The hooks must work even if no peer connection exists yet.

## Compatibility

- Keep existing `window.__RTCTrainingTestHooks` methods.
- Keep existing NACK behavior.
- Keep mobile action bar behavior.
- Do not change WebRTC or Dashboard API routes.

