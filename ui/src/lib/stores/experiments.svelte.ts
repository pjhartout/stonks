import { fetchExperiments, fetchMetricKeys, fetchMetrics, fetchRuns } from "../api/client";
import { connectSSE } from "../api/sse";
import type { Experiment, MetricSeries, Run } from "../types";

// Reactive state using Svelte 5 runes
let experiments = $state<Experiment[]>([]);
let selectedExperimentId = $state<string | null>(null);
let runs = $state<Run[]>([]);
let selectedRunId = $state<string | null>(null);
let metricKeys = $state<string[]>([]);
let metricData = $state<Map<string, MetricSeries>>(new Map());
let loading = $state(false);
let error = $state<string | null>(null);

let sseCleanup: (() => void) | null = null;

export function getExperiments() {
  return experiments;
}

export function getSelectedExperimentId() {
  return selectedExperimentId;
}

export function getRuns() {
  return runs;
}

export function getSelectedRunId() {
  return selectedRunId;
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
  selectedRunId = null;
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
        // Refetch metrics for the updated run if it's selected
        if (selectedRunId === event.run_id) {
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

export async function selectRun(id: string) {
  selectedRunId = id;
  await loadMetricsForRun(id);
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

async function loadMetricsForRun(runId: string) {
  try {
    const newKeys = await fetchMetricKeys(runId);
    const newData = new Map<string, MetricSeries>();
    const promises = newKeys.map(async (key) => {
      const series = await fetchMetrics(runId, key, 1000);
      newData.set(key, series);
    });
    await Promise.all(promises);

    // Update data FIRST so metricData.has(key) is true when keys are evaluated
    for (const [key, series] of newData) {
      metricData.set(key, series);
    }
    metricData = metricData;

    // Only reassign keys if the set actually changed (avoids unnecessary DOM churn)
    if (!arraysEqual(newKeys, metricKeys)) {
      metricKeys = newKeys;
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load metrics";
  }
}

export function cleanup() {
  if (sseCleanup) {
    sseCleanup();
    sseCleanup = null;
  }
}
