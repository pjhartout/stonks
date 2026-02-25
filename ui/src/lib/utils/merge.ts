import type { RunSeries } from "../types";

/**
 * Merge multiple run series onto a shared x-axis for uPlot.
 *
 * uPlot requires all series to share one x-axis array. When runs log at
 * different steps, we compute the sorted union of all step values and
 * NaN-fill where a run has no data for a given step.
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
    const values = new Float64Array(d.values.length);
    for (let i = 0; i < d.values.length; i++) {
      values[i] = d.values[i] ?? NaN;
    }
    return [steps, values];
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

  // For each run, create an aligned values array
  const aligned: Float64Array[] = [];
  for (const run of runs) {
    const values = new Float64Array(allSteps.length).fill(NaN);
    const d = run.data;
    for (let i = 0; i < d.steps.length; i++) {
      const idx = stepIndex.get(d.steps[i]);
      if (idx !== undefined) {
        values[idx] = d.values[i] ?? NaN;
      }
    }
    aligned.push(values);
  }

  return [sharedSteps, ...aligned] as [Float64Array, ...Float64Array[]];
}
