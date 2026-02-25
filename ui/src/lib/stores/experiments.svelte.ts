import { fetchExperiments, fetchMetricKeys, fetchMetrics, fetchRuns, patchRun } from "../api/client";
import { connectSSE } from "../api/sse";
import type { Experiment, MetricSeries, Run } from "../types";
import { MAX_SELECTED_RUNS } from "../utils/colors";

const COLOR_STORAGE_KEY = "stonks:run-colors";

// Reactive state using Svelte 5 runes
let experiments = $state<Experiment[]>([]);
let selectedExperimentId = $state<string | null>(null);
let runs = $state<Run[]>([]);
let selectedRunIds = $state<Set<string>>(new Set());
let primaryRunId = $state<string | null>(null);
let metricKeys = $state<string[]>([]);
// Nested: metricKey -> runId -> MetricSeries
let metricData = $state<Map<string, Map<string, MetricSeries>>>(new Map());
let colorOverrides = $state<Map<string, string>>(loadColorOverrides());
let loading = $state(false);
let error = $state<string | null>(null);

let sseCleanup: (() => void) | null = null;

function loadColorOverrides(): Map<string, string> {
  try {
    const raw = localStorage.getItem(COLOR_STORAGE_KEY);
    if (raw) return new Map(JSON.parse(raw));
  } catch { /* ignore */ }
  return new Map();
}

function saveColorOverrides() {
  localStorage.setItem(COLOR_STORAGE_KEY, JSON.stringify([...colorOverrides]));
}

export function getExperiments() {
  return experiments;
}

export function getSelectedExperimentId() {
  return selectedExperimentId;
}

export function getRuns() {
  return runs;
}

export function getSelectedRunIds() {
  return selectedRunIds;
}

export function getPrimaryRunId() {
  return primaryRunId;
}

export function getMetricKeys() {
  return metricKeys;
}

export function getMetricData() {
  return metricData;
}

export function getLoading() {
  return loading;
}

export function getError() {
  return error;
}

export async function loadExperiments() {
  loading = true;
  error = null;
  try {
    experiments = await fetchExperiments();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load experiments";
  } finally {
    loading = false;
  }
}

export async function selectExperiment(id: string) {
  selectedExperimentId = id;
  selectedRunIds = new Set();
  primaryRunId = null;
  metricKeys = [];
  metricData = new Map();
  loading = true;
  error = null;

  // Disconnect previous SSE
  if (sseCleanup) {
    sseCleanup();
    sseCleanup = null;
  }

  try {
    runs = await fetchRuns(id);

    // Connect SSE for live updates
    sseCleanup = connectSSE(id, {
      onRunUpdate: (event) => {
        runs = runs.map((r) =>
          r.id === event.run_id ? { ...r, status: event.status, ended_at: event.ended_at } : r,
        );
      },
      onMetricsUpdate: async (event) => {
        // Refetch metrics for any selected run that received an update
        if (selectedRunIds.has(event.run_id)) {
          await loadMetricsForRun(event.run_id);
        }
      },
    });
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load runs";
  } finally {
    loading = false;
  }
}

/** Select a run as primary (row click). Also adds to selection set. */
export async function selectRun(id: string) {
  primaryRunId = id;
  if (!selectedRunIds.has(id)) {
    if (selectedRunIds.size >= MAX_SELECTED_RUNS) return;
    selectedRunIds = new Set([...selectedRunIds, id]);
    await loadMetricsForRun(id);
  }
}

/** Toggle a run in/out of the comparison set (checkbox click). */
export async function toggleRunSelection(id: string) {
  if (selectedRunIds.has(id)) {
    removeRunMetrics(id);
    const next = new Set(selectedRunIds);
    next.delete(id);
    selectedRunIds = next;
    // If we removed the primary, pick another or null
    if (primaryRunId === id) {
      const remaining = [...selectedRunIds];
      primaryRunId = remaining.length > 0 ? remaining[0] : null;
    }
  } else {
    if (selectedRunIds.size >= MAX_SELECTED_RUNS) return;
    selectedRunIds = new Set([...selectedRunIds, id]);
    if (!primaryRunId) primaryRunId = id;
    await loadMetricsForRun(id);
  }
}

/** Recompute the union of metric keys across all selected runs. */
function recomputeMetricKeys() {
  metricKeys = [...metricData.keys()].sort();
}

async function loadMetricsForRun(runId: string) {
  try {
    const downsample = Math.max(200, Math.floor(1000 / Math.max(selectedRunIds.size, 1)));
    const runKeys = await fetchMetricKeys(runId);
    const fetched = new Map<string, MetricSeries>();
    const promises = runKeys.map(async (key) => {
      const series = await fetchMetrics(runId, key, downsample);
      fetched.set(key, series);
    });
    await Promise.all(promises);

    // Merge this run's data into the nested map (data first, then keys)
    const updated = new Map(metricData);
    for (const [key, series] of fetched) {
      const existing = updated.get(key) ?? new Map();
      existing.set(runId, series);
      updated.set(key, existing);
    }
    metricData = updated;

    recomputeMetricKeys();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load metrics";
  }
}

/** Remove a run's data from all metric keys. */
function removeRunMetrics(runId: string) {
  const updated = new Map<string, Map<string, MetricSeries>>();
  for (const [key, runMap] of metricData) {
    const filtered = new Map(runMap);
    filtered.delete(runId);
    if (filtered.size > 0) {
      updated.set(key, filtered);
    }
  }
  metricData = updated;
  recomputeMetricKeys();
}

export function getColorOverrides() {
  return colorOverrides;
}

export function setRunColor(runId: string, color: string) {
  colorOverrides = new Map(colorOverrides);
  colorOverrides.set(runId, color);
  saveColorOverrides();
}

export async function renameRun(runId: string, name: string) {
  try {
    const updated = await patchRun(runId, { name: name || null });
    runs = runs.map((r) => (r.id === runId ? { ...r, name: updated.name } : r));
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to rename run";
  }
}

export function cleanup() {
  if (sseCleanup) {
    sseCleanup();
    sseCleanup = null;
  }
}
