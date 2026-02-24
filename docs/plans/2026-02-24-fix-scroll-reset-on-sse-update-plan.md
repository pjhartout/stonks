---
title: "fix: Preserve scroll position during SSE metric updates"
type: fix
status: completed
date: 2026-02-24
---

# fix: Preserve scroll position during SSE metric updates

Every time an SSE metric update arrives (~1s for running experiments), the dashboard scrolls back to the top. This makes it impossible to inspect charts or config lower on the page while an experiment is running.

## Root Cause

Two issues in `ui/src/lib/stores/experiments.svelte.ts` `loadMetricsForRun()` (lines 104-117):

**Factor A -- Temporal gap causes DOM destroy/recreate cycle:**
`metricKeys` is reassigned (line 106) before `metricData` is populated (line 113). During the async gap, `{#if metricData.has(key)}` in `App.svelte` evaluates to `false` for every chart, unmounting all `MetricChart` components. When `metricData` is set moments later, they remount -- resetting scroll.

**Factor B -- Full state replacement triggers unnecessary re-renders:**
Both `metricKeys` and `metricData` are replaced with entirely new objects on every update, even when content is identical. This causes Svelte's `$effect` in `MetricChart.svelte` to destroy and recreate uPlot chart instances, mutating the DOM and resetting scroll.

## Acceptance Criteria

- [x] Scroll position is preserved when SSE metric updates arrive
- [x] Charts update with new data points without being destroyed/recreated
- [x] No visible flicker or flash when metrics refresh
- [x] Existing tests pass; add a test if feasible for the incremental update path

## Fix Strategy

### 1. Eliminate the temporal gap in `experiments.svelte.ts`

In `loadMetricsForRun()`, fetch everything first, then assign state atomically:

```typescript
// ui/src/lib/stores/experiments.svelte.ts -- loadMetricsForRun()
const newKeys = await fetchMetricKeys(runId);
// ... fetch all series into newData Map ...
metricData = newData;    // assign data FIRST
metricKeys = newKeys;    // then keys (so metricData.has(key) is always true)
```

### 2. Update in-place instead of replacing wholesale in `experiments.svelte.ts`

Only update `metricKeys` when keys actually change. Merge new metric series into the existing `metricData` Map rather than replacing it:

```typescript
// ui/src/lib/stores/experiments.svelte.ts -- loadMetricsForRun()
// Only reassign metricKeys if the set of keys changed
if (!arraysEqual(newKeys, metricKeys)) {
  metricKeys = newKeys;
}

// Merge into existing map instead of replacing
for (const [key, series] of newData) {
  metricData.set(key, series);
}
// Trigger Svelte reactivity on the map
metricData = metricData;
```

### 3. Guard chart recreation in `MetricChart.svelte`

The `$effect` block (lines 208-226) should only call `chart.setData()` when the chart already exists, and only create a new chart on first mount. Avoid the destroy/recreate cycle on data updates.

## Key Files

| File | Change |
|------|--------|
| `ui/src/lib/stores/experiments.svelte.ts` | Atomic state assignment, in-place map updates |
| `ui/src/lib/components/MetricChart.svelte` | Guard `$effect` to avoid chart recreation |
| `ui/src/App.svelte` | No changes expected (benefits from upstream fixes) |

## Sources

- Root cause traced through: `ui/src/lib/stores/experiments.svelte.ts:104-117`, `ui/src/App.svelte:113-118`, `ui/src/lib/components/MetricChart.svelte:208-226`
- SSE backend: `stonks/server/routes/stream.py` (polls every 1s)
