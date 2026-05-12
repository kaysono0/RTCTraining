# Simplified ABR

## Goal

Add a simplified ABR mode for the WebRTC experiment page. ABR only adjusts video sender `maxBitrate`; it does not change resolution, FPS, codec, SDP, or receiver behavior.

## Scope

Included:

- ABR mode switch: off / on.
- User configurable min / max / step / interval / loss threshold / RTT threshold.
- ABR decision function that can be tested without a real peer connection.
- Runtime application through the existing manual bitrate module.
- Stats fields recording ABR mode, target bitrate, and last decision.

Excluded:

- Test sessions.
- Session CSV output.
- Dashboard CSV comparison.
- Browser weak-network automation.

## UI

The WebRTC page adds ABR controls in the existing `room-controls` area:

- `#abrModeSelect`: `off` or `on`.
- `#abrMinBitrateInput`: min kbps.
- `#abrMaxBitrateInput`: max kbps.
- `#abrStepKbpsInput`: step kbps.
- `#abrLossThresholdInput`: percent.
- `#abrRttThresholdInput`: milliseconds.
- `#abrModeState`: current ABR state.

Defaults:

```text
off
min 300 kbps
max 1500 kbps
step 150 kbps
loss threshold 5%
RTT threshold 300 ms
interval 1000 ms
```

## Decision Rules

ABR reads the latest sample metrics from `shared.state.latestStats`.

If no latest sample exists:

```text
abr_waiting
```

If `packet_loss_rate >= lossThreshold` or `rtt_ms >= rttThreshold`:

```text
decrease
target = max(min, current - step)
```

If `packet_loss_rate < lossThreshold / 2`, `rtt_ms < rttThreshold / 2`, and `fps >= 20`:

```text
increase
target = min(max, current + step)
```

Otherwise:

```text
hold
target = current
```

The current bitrate starts at `maxBitrate` when ABR is enabled unless a manual target already exists inside the configured range.

## State

Shared frontend state adds:

```javascript
abrMode: "off" | "on"
abrTargetBitrateBps: null | number
abrLastDecision: "off" | "waiting" | "increase" | "decrease" | "hold"
abrConfig: {
  minBitrateKbps,
  maxBitrateKbps,
  stepKbps,
  intervalMs,
  lossThresholdPercent,
  rttThresholdMs
}
```

When ABR is on, `bitrateMode` becomes `abr`. When ABR is off, bitrate returns to auto unless the user later applies manual bitrate.

## Stats

Each stats sample records:

```javascript
abr_mode
abr_target_bitrate_bps
abr_decision
```

The existing `bitrate_mode` field can be `auto`, `manual`, or `abr`.

## Test Hooks

`window.__RTCTrainingTestHooks` adds:

```javascript
setAbrMode(mode)
runAbrDecision(metrics)
getAbrMode()
getAbrTargetBitrateBps()
getAbrLastDecision()
```

`runAbrDecision(metrics)` is deterministic and returns the decision result.

