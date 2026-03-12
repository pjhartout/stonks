import type { RunSeries } from "../types";

/**
 * Check if any run in the series has min/max band data.
 */
export function hasBands(runs: RunSeries[]): boolean {
  return runs.some((r) => r.data.values_min && r.data.values_max);
}

/**
 * Merge multiple run series onto a shared x-axis for uPlot.
 *
 * uPlot requires all series to share one x-axis array. When runs log at
 * different steps, we compute the sorted union of all step values and
 * NaN-fill where a run has no data for a given step.
 *
 * When a run has values_min/values_max (rank-aggregated), we output three
 * data arrays per run: [values, values_min, values_max].
 *
 * Returns [sharedSteps, ...perRunValues] as Float64Arrays.
 */
export function mergeRunSeries(
  runs: RunSeries[],
): [Float64Array, ...Float64Array[]] {
  if (runs.length === 0) {
    return [new Float64Array(0)] as [Float64Array, ...Float64Array[]];
  }

  // Fast path: single run — no merging needed
  if (runs.length === 1) {
    const d = runs[0].data;
    const steps = new Float64Array(d.steps);
    const values = toFloat64(d.values);
    const arrays: Float64Array[] = [steps, values];
    if (d.values_min && d.values_max) {
      arrays.push(toFloat64(d.values_min));
      arrays.push(toFloat64(d.values_max));
    }
    return arrays as [Float64Array, ...Float64Array[]];
  }

  // Collect all unique steps across runs into a sorted array
  const stepSet = new Set<number>();
  for (const run of runs) {
    for (const s of run.data.steps) {
      stepSet.add(s);
    }
  }
  const allSteps = Array.from(stepSet).sort((a, b) => a - b);
  const sharedSteps = new Float64Array(allSteps);

  // Build a step→index lookup for the shared axis
  const stepIndex = new Map<number, number>();
  for (let i = 0; i < allSteps.length; i++) {
    stepIndex.set(allSteps[i], i);
  }

  // For each run, create aligned value arrays
  const aligned: Float64Array[] = [];
  for (const run of runs) {
    const d = run.data;
    const values = alignToSteps(d.values, d.steps, allSteps.length, stepIndex);
    aligned.push(values);
    if (d.values_min && d.values_max) {
      aligned.push(alignToSteps(d.values_min, d.steps, allSteps.length, stepIndex));
      aligned.push(alignToSteps(d.values_max, d.steps, allSteps.length, stepIndex));
    }
  }

  return [sharedSteps, ...aligned] as [Float64Array, ...Float64Array[]];
}

function toFloat64(arr: (number | null)[]): Float64Array {
  const out = new Float64Array(arr.length);
  for (let i = 0; i < arr.length; i++) {
    out[i] = arr[i] ?? NaN;
  }
  return out;
}

function alignToSteps(
  values: (number | null)[],
  steps: number[],
  len: number,
  stepIndex: Map<number, number>,
): Float64Array {
  const out = new Float64Array(len).fill(NaN);
  for (let i = 0; i < steps.length; i++) {
    const idx = stepIndex.get(steps[i]);
    if (idx !== undefined) {
      out[idx] = values[i] ?? NaN;
    }
  }
  return out;
}
