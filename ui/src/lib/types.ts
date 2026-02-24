export interface Experiment {
  id: string;
  name: string;
  description: string | null;
  created_at: number;
  run_count: number;
}

export interface Run {
  id: string;
  experiment_id: string;
  name: string | null;
  status: "running" | "completed" | "failed" | "interrupted";
  config: Record<string, unknown> | null;
  created_at: number;
  ended_at: number | null;
  last_heartbeat: number | null;
}

export interface MetricSeries {
  key: string;
  steps: number[];
  values: (number | null)[];
  timestamps: number[];
}

export interface RunSeries {
  runId: string;
  runName: string;
  color: string;
  data: MetricSeries;
}

export interface RunUpdateEvent {
  run_id: string;
  status: Run["status"];
  name: string | null;
  created_at: number;
  ended_at: number | null;
}

export interface MetricsUpdateEvent {
  run_id: string;
  last_heartbeat: number;
}
