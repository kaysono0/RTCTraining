# Dashboard Layout Redesign

## Goal

Redesign the Dashboard page as a diagnostic workstation. The page should prioritize controls, current state, live stats, and the wide history table according to content size instead of placing four panels in an equal grid.

## Layout

Desktop layout:

```text
Header
Control Bar
Summary Strip
Main Grid
History Section
```

Mobile layout:

```text
Header
Control Bar
Summary Cards
Latest Stats
Peer Pair
Mesh Topology
History Table
```

## Sections

### Header

The header keeps the title, service state, and service check action. It remains compact so the current diagnostic content stays visible.

Required elements:

- `#serviceState`
- `#checkServiceButton`

### Control Bar

The WebRTC origin and room selector move out of the old service/stats cards into a single control area. This area owns the main user inputs and the destructive stats clear action.

Required elements:

- `#webrtcOriginInput`
- `#statsRoomInput`
- `#clearStatsButton`

### Summary Strip

The summary strip shows the small state values that do not need large cards.

Required elements:

- `#roomSummary`
- `#statsState`
- `#statsRefreshState`
- `#meshTopologyState`
- `#csvState`

The strip also reserves a `#nackSummary` element. JavaScript may update it from the latest sample. Empty or missing NACK values must display as `NACK: -`.

### Main Grid

The main grid uses a narrow left column and wider right column on desktop.

Left column:

- Peer pair list
- Mesh topology list

Right column:

- Latest stats panel

The existing `#latestStatsPanel` remains a `dl`, but its content should be grouped visually by metric category through CSS. Existing `dt` and `dd` rendering can stay unchanged for this iteration.

Required elements:

- `#peerPairList`
- `#meshTopology`
- `#latestStatsPanel`

### History Section

The stats history table gets a full-width section because it has many columns. It must support horizontal scrolling and sticky table headers.

Required elements:

- `#statsHistoryTable`

## Responsive Rules

At widths below `760px`:

- Header stacks vertically.
- Control bar becomes a single column.
- Summary strip becomes two columns.
- Main grid becomes one column.
- Latest stats should appear before peer and mesh lists.
- History table remains horizontally scrollable.
- Buttons and inputs are full width.

## Compatibility

The redesign must not change Dashboard API behavior.

The redesign must preserve existing IDs and test hooks:

- `window.__RTCTrainingDashboardTestHooks`
- `#serviceState`
- `#checkServiceButton`
- `#webrtcOriginInput`
- `#roomSummary`
- `#statsRoomInput`
- `#clearStatsButton`
- `#statsState`
- `#statsRefreshState`
- `#peerPairList`
- `#latestStatsPanel`
- `#statsHistoryTable`
- `#meshTopologyState`
- `#meshTopology`
- `#csvState`

## Tests

Add tests before implementation:

- The Dashboard HTML declares the workstation layout containers.
- The Dashboard HTML keeps all existing IDs.
- The Dashboard page renders the wide history table in a full-width section.
- Mobile viewport verifies header, controls, latest stats, peer/mesh, and history are visible without horizontal page overflow; the table itself may scroll horizontally inside its own section.

