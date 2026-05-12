# Dashboard CSV Metric Selection

## Scope

Enhance Dashboard CSV comparison with a selectable trend metric.

## UI

Add:

- `#csvMetricSelect`

Supported metrics:

- RTT
- Loss
- Jitter
- Bitrate
- FPS

## Behavior

After CSV analysis, `#csvTrendComparison` shows the best file for the selected metric.

Best direction:

- lower is better: RTT, loss, jitter
- higher is better: bitrate, FPS

Changing the metric updates the trend result without re-reading CSV files.

## Test Hook

Expose:

- `setCsvMetric(metricName)`
