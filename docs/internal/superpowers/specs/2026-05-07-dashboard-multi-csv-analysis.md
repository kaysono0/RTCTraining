# Dashboard Multi CSV Analysis

## Scope

Add the first Dashboard multi CSV comparison slice.

This slice runs fully in the browser:

- Multi CSV file selection.
- CSV schema validation.
- Per-file sample statistics.
- Basic trend comparison.

It does not persist uploaded CSV files on the server.

## Required Fields

Dashboard validates these CSV fields:

- `sample_index`
- `timestamp`
- `room_id`
- `test_session_id`
- `peer_id`
- `remote_peer_id`
- `rtt_ms`
- `packet_loss_rate`
- `jitter_ms`
- `bitrate_kbps`
- `fps`
- `nack_mode`
- `abr_mode`

## UI

New Dashboard elements:

- `#csvFileInput`
- `#csvAnalyzeButton`
- `#csvValidationPanel`
- `#csvComparisonTable`
- `#csvTrendComparison`

## Metrics

Per file:

- sample count
- room/session/peer/remote labels
- average RTT
- average packet loss rate
- average bitrate
- average FPS

Trend comparison:

- lowest average RTT
- lowest average loss
- highest average bitrate

## Test Hooks

Expose:

- `analyzeCsvTexts(entries)`
- `analyzeSelectedCsvFiles()`
