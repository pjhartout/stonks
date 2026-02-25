import type { Experiment, MetricSeries, Run } from "../types";

const BASE = "/api";

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  const resp = await fetch(url.toString());
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchExperiments(): Promise<Experiment[]> {
  return get<Experiment[]>("/experiments");
}

export async function fetchRuns(experimentId: string): Promise<Run[]> {
  return get<Run[]>(`/experiments/${experimentId}/runs`);
}

export async function fetchMetricKeys(runId: string): Promise<string[]> {
  return get<string[]>(`/runs/${runId}/metric-keys`);
}

export async function patchRun(
  runId: string,
  fields: { name?: string | null },
): Promise<Run> {
  const resp = await fetch(`${BASE}/runs/${runId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchMetrics(
  runId: string,
  key: string,
  downsample?: number,
): Promise<MetricSeries> {
  const params: Record<string, string> = { key };
  if (downsample) {
    params.downsample = String(downsample);
  }
  return get<MetricSeries>(`/runs/${runId}/metrics`, params);
}
