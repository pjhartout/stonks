---
title: "feat: Multi-run metric overlay on charts"
type: feat
status: completed
date: 2026-02-24
---

# feat: Multi-run metric overlay on charts

## Overview

Allow users to select multiple runs within an experiment and overlay their metric curves on the same chart. This enables side-by-side comparison of runs that train simultaneously with the same metrics (e.g., hyperparameter sweeps, k-fold splits).

## Problem Statement / Motivation

Currently the dashboard only supports viewing one run's metrics at a time. When running parallel experiments with different hyperparameters, users must click between runs to mentally compare loss curves. Overlaying curves on a shared chart is the standard approach in tools like W&B and TensorBoard for a reason — it makes differences immediately visible.

## Proposed Solution

### Interaction model: Checkbox multi-select in RunTable

Add a checkbox column to `RunTable`. Clicking a row still selects it as the "primary" run (shown in detail). Clicking the checkbox toggles a run into/out of the comparison set. This is the W&B/MLflow pattern — more discoverable than Cmd+Click.

### Data model change

Replace the flat `Map<string, MetricSeries>` with a nested structure:

```
selectedRunIds: Set<string>              // replaces selectedRunId: string | null
metricData: Map<string, Map<string, MetricSeries>>  // outer=metricKey, inner=runId
```

This preserves the existing chart-per-key layout while adding the run dimension.

### Chart overlay via uPlot

`MetricChart` accepts an array of named series instead of a single `MetricSeries`. Steps are merged into a shared x-axis using a sorted union with NaN-fill for missing values. uPlot natively supports `[xValues, yValues1, yValues2, ...]`.

### Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Multi-select UX | Checkbox column | More discoverable than modifier keys |
| Metric key policy | Union (show all keys from any selected run) | A chart with 1 of 3 runs is still useful |
| Max selected runs | 8 | Balances color palette, legend readability, API load |
| Chart lifecycle on selection change | Destroy + recreate | Simpler; selection changes are user-driven, not per-second SSE |
| Color assignment | Stable per run ID (hash-based index into palette) | Colors don't shift when runs are deselected |
| Hardware panel (`sys/` metrics) | Out of scope — remains single-run | Overlaid CPU charts for 8 runs isn't useful |
| URL state | Out of scope for MVP | Can be added later without architectural impact |
| Tooltip | Multi-line with all runs' values + color swatch | Standard pattern for multi-series charts |
| Downsample budget | `max(200, floor(1000 / selectedRunCount))` per series | Prevents rendering 8000+ points per chart |

## Technical Approach

### 1. Store layer (`experiments.svelte.ts`)

- Replace `selectedRunId: string | null` with `selectedRunIds = $state<Set<string>>(new Set())`
- Keep a `primaryRunId` for the header label and ConfigComparison focus
- New `metricData: Map<string, Map<string, MetricSeries>>` — outer key = metric key, inner key = run ID
- `toggleRunSelection(id: string)` — adds/removes from set, fetches/evicts that run's metrics
- `loadMetricsForRun` becomes additive — merges one run's data into the nested map without touching other runs
- `removeRunMetrics(runId: string)` — removes a run's data from the nested map
- SSE `onMetricsUpdate` checks `selectedRunIds.has(event.run_id)` instead of `===`
- Debounce SSE-triggered refetches by 500ms per run to avoid thundering herd

### 2. Types (`types.ts`)

Add a wrapper for chart consumption:

```typescript
export interface RunSeries {
  runId: string;
  runName: string;
  color: string;
  data: MetricSeries;
}
```

### 3. RunTable (`RunTable.svelte`)

- Add `selectedIds: Set<string>` prop (replaces `selectedId`)
- Add checkbox column (first column)
- Checkbox click → `onToggle(id)` (add/remove from comparison)
- Row click → `onSelect(id)` (set as primary, also adds to selection)
- Highlight all rows in `selectedIds`, with primary row having a stronger indicator
- Show selection count badge: "3 of 12 selected"
- Disable checkboxes when 8 runs are already selected (with tooltip explaining limit)

### 4. MetricChart (`MetricChart.svelte`)

- Change props from `{ series: MetricSeries; title: string }` to `{ runs: RunSeries[]; title: string }`
- New `mergeData(runs: RunSeries[])` function:
  - Compute sorted union of all step arrays → shared x-axis
  - For each run, produce a values array aligned to the shared x-axis (NaN for missing steps)
  - Return `[Float64Array, ...Float64Array[]]`
- Update `createChart` to configure N series entries with each run's color
- Update tooltip plugin to iterate `u.data[1..N]` and show all values with color swatches
- Enable legend (`legend: { show: true }`) with run names
- On selection change: destroy chart and recreate (simpler than `addSeries`/`delSeries`)

### 5. Color palette

Define 8 distinct colors as CSS custom properties, optimized for dark background and colorblind accessibility:

```css
--chart-color-0: #6366f1;  /* indigo (existing) */
--chart-color-1: #f59e0b;  /* amber */
--chart-color-2: #10b981;  /* emerald */
--chart-color-3: #ef4444;  /* red */
--chart-color-4: #8b5cf6;  /* violet */
--chart-color-5: #06b6d4;  /* cyan */
--chart-color-6: #f97316;  /* orange */
--chart-color-7: #ec4899;  /* pink */
```

Color is assigned by hashing the run ID to a palette index, so colors are stable across deselect/reselect.

### 6. App.svelte

- Derive `metricKeys` as union of all keys across selected runs
- Build `RunSeries[]` per metric key from the nested `metricData` map
- Pass `runs={selectedRuns}` to `ConfigComparison` (already multi-run ready)
- Update metrics section header: "Metrics — {primaryRun.name}" or "Comparing N runs" when multiple selected
- `HardwarePanel` remains scoped to the primary run only

### 7. Step alignment function (pure, testable)

```typescript
function mergeStepAxes(seriesList: MetricSeries[]): {
  steps: Float64Array;
  aligned: Float64Array[];  // one per input series
}
```

This is a pure function with no UI dependencies. Extract it to a utility file and unit test it in isolation.

## Acceptance Criteria

- [x]Users can select multiple runs via checkboxes in the RunTable
- [x]Selecting multiple runs overlays their metric curves on the same chart with distinct colors
- [x]A legend identifies which color maps to which run
- [x]Tooltip shows all runs' values at the cursor position
- [x]SSE live updates work for all selected runs simultaneously
- [x]Deselecting a run removes its curve from all charts
- [x]Runs with partially overlapping metrics show charts for the union of keys
- [x]Runs with different step ranges are correctly aligned with NaN gaps
- [x]Maximum of 8 runs can be selected simultaneously
- [x]ConfigComparison table shows all selected runs side-by-side
- [x]Hardware panel remains single-run (primary selected run)
- [x]No scroll position reset or chart flicker during SSE updates (preserves PR #6 fix)
- [x]`svelte-check` and `bun run build` pass with no errors

## Dependencies & Risks

- **Step alignment complexity**: Merging heterogeneous step arrays is the trickiest part. Isolate in a pure function and test edge cases (empty arrays, single point, fully disjoint ranges).
- **API fan-out**: 8 runs x 20 metrics = 160 concurrent requests on selection. Mitigate with downsample scaling and debounced SSE refetches.
- **uPlot series config is immutable after creation**: Cannot dynamically add/remove series. Must destroy and recreate chart when selection set changes. This is acceptable since selection changes are user-initiated (not per-second).
- **Backward compatibility**: The single-run case (1 run selected) must look and behave identically to the current UI. This is the natural fallback of the multi-run design with `runs.length === 1`.

## Sources

- Current store: `ui/src/lib/stores/experiments.svelte.ts`
- Current chart: `ui/src/lib/components/MetricChart.svelte`
- RunTable: `ui/src/lib/components/RunTable.svelte`
- ConfigComparison (already multi-run): `ui/src/lib/components/ConfigComparison.svelte`
- API endpoints: `stonks/server/routes/metrics.py`
- Scroll-fix learnings (in-place updates, chart lifecycle): PR #6
