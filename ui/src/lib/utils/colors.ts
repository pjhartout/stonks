/** Chart color palette — 8 distinct colors for multi-run overlays. */
export const CHART_COLORS = [
  "#6366f1", // indigo
  "#f59e0b", // amber
  "#10b981", // emerald
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f97316", // orange
  "#ec4899", // pink
];

export const MAX_SELECTED_RUNS = 8;

/**
 * Assign a stable color to a run based on its ID.
 * Uses a simple hash so the same run always gets the same color.
 * If an override map is provided, it takes precedence.
 */
export function colorForRun(runId: string, overrides?: Map<string, string>): string {
  if (overrides?.has(runId)) return overrides.get(runId)!;
  let hash = 0;
  for (let i = 0; i < runId.length; i++) {
    hash = (hash * 31 + runId.charCodeAt(i)) | 0;
  }
  return CHART_COLORS[Math.abs(hash) % CHART_COLORS.length];
}
