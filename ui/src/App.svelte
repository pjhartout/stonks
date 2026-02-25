<script lang="ts">
  import { onMount } from "svelte";
  import ExperimentList from "./lib/components/ExperimentList.svelte";
  import RunTable from "./lib/components/RunTable.svelte";
  import MetricChart from "./lib/components/MetricChart.svelte";
  import ConfigComparison from "./lib/components/ConfigComparison.svelte";
  import EmptyState from "./lib/components/EmptyState.svelte";
  import HardwarePanel from "./lib/components/HardwarePanel.svelte";
  import type { RunSeries } from "./lib/types";
  import { colorForRun } from "./lib/utils/colors";
  import {
    getExperiments,
    getSelectedExperimentId,
    getRuns,
    getSelectedRunIds,
    getPrimaryRunId,
    getMetricKeys,
    getMetricData,
    getColorOverrides,
    getLoading,
    getError,
    loadExperiments,
    selectExperiment,
    selectRun,
    toggleRunSelection,
    setRunColor,
    renameRun,
    cleanup,
  } from "./lib/stores/experiments.svelte";

  onMount(() => {
    loadExperiments();
    return cleanup;
  });

  let experiments = $derived(getExperiments());
  let selectedExperimentId = $derived(getSelectedExperimentId());
  let runs = $derived(getRuns());
  let selectedRunIds = $derived(getSelectedRunIds());
  let primaryRunId = $derived(getPrimaryRunId());
  let metricKeys = $derived(getMetricKeys());
  let metricData = $derived(getMetricData());
  let colorOverrides = $derived(getColorOverrides());
  let loading = $derived(getLoading());
  let error = $derived(getError());

  let primaryRun = $derived(runs.find((r) => r.id === primaryRunId) ?? null);
  let selectedRuns = $derived(runs.filter((r) => selectedRunIds.has(r.id)));

  /** Separate hardware (sys/) keys from training keys. */
  let trainingKeys = $derived(metricKeys.filter((k) => !k.startsWith("sys/")));
  let hardwareKeys = $derived(metricKeys.filter((k) => k.startsWith("sys/")));

  /** Hardware metric key -> RunSeries[] across all selected runs (same overlay pattern as training). */
  let hardwareByKey = $derived.by(() => {
    const map = new Map<string, RunSeries[]>();
    for (const key of hardwareKeys) {
      const runMap = metricData.get(key);
      if (!runMap) continue;
      const series: RunSeries[] = [];
      for (const run of selectedRuns) {
        const data = runMap.get(run.id);
        if (data) {
          series.push({
            runId: run.id,
            runName: run.name || run.id.slice(0, 8),
            color: colorForRun(run.id, colorOverrides),
            data,
          });
        }
      }
      if (series.length > 0) map.set(key, series);
    }
    return map;
  });

  /** Group training metric keys by prefix (e.g. train/loss -> train). */
  let groupedKeys = $derived.by(() => {
    const groups = new Map<string, string[]>();
    for (const key of trainingKeys) {
      const slash = key.indexOf("/");
      const group = slash > 0 ? key.slice(0, slash) : "metrics";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)!.push(key);
    }
    return groups;
  });

  /** Reactive map of metric key -> RunSeries[] across all selected runs. */
  let runsByKey = $derived.by(() => {
    const map = new Map<string, RunSeries[]>();
    for (const key of trainingKeys) {
      const runMap = metricData.get(key);
      if (!runMap) continue;
      const series: RunSeries[] = [];
      for (const run of selectedRuns) {
        const data = runMap.get(run.id);
        if (data) {
          series.push({
            runId: run.id,
            runName: run.name || run.id.slice(0, 8),
            color: colorForRun(run.id, colorOverrides),
            data,
          });
        }
      }
      if (series.length > 0) {
        map.set(key, series);
      }
    }
    return map;
  });

  /** Header text for the metrics section. */
  let metricsHeader = $derived.by(() => {
    if (selectedRuns.length === 0) return "";
    if (selectedRuns.length === 1) {
      const r = selectedRuns[0];
      return `Metrics \u2014 ${r.name || r.id.slice(0, 8)}`;
    }
    return `Comparing ${selectedRuns.length} runs`;
  });
</script>

<div class="app">
  <ExperimentList
    {experiments}
    selectedId={selectedExperimentId}
    onSelect={selectExperiment}
  />

  <main class="content">
    {#if error}
      <div class="error-banner">{error}</div>
    {/if}

    {#if loading}
      <div class="loading">Loading...</div>
    {:else if !selectedExperimentId}
      <div class="center">
        <EmptyState
          title="Select an experiment"
          message="Choose an experiment from the sidebar to view its runs and metrics."
        />
      </div>
    {:else}
      <div class="experiment-view">
        <section class="runs-section">
          <h2>Runs</h2>
          <RunTable
            {runs}
            selectedIds={selectedRunIds}
            primaryId={primaryRunId}
            {colorOverrides}
            onSelect={selectRun}
            onToggle={toggleRunSelection}
            onRename={renameRun}
            onColorChange={setRunColor}
          />
        </section>

        {#if selectedRuns.length > 0}
          <section class="metrics-section">
            <h2>{metricsHeader}</h2>

            {#if hardwareByKey.size > 0}
              <HardwarePanel metricsByKey={hardwareByKey} />
            {/if}

            {#if metricKeys.length === 0}
              <EmptyState
                title="No metrics"
                message="This run has no logged metrics yet."
              />
            {:else}
              {#each [...groupedKeys] as [group, keys] (group)}
                <div class="metric-group">
                  <h3 class="group-label">{group}</h3>
                  <div class="charts-grid">
                    {#each keys as key (key)}
                      {#if runsByKey.has(key)}
                        <MetricChart
                          runs={runsByKey.get(key)!}
                          title={key}
                        />
                      {/if}
                    {/each}
                  </div>
                </div>
              {/each}

              <ConfigComparison runs={selectedRuns} />
            {/if}
          </section>
        {/if}
      </div>
    {/if}
  </main>
</div>

<style>
  .app {
    display: flex;
    height: 100%;
    width: 100%;
  }
  .content {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
  }
  .center {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 0.9rem;
  }
  .error-banner {
    background: var(--red);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: var(--radius);
    margin-bottom: 1rem;
    font-size: 0.85rem;
  }
  .experiment-view {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .runs-section, .metrics-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  h2 {
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .metric-group {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .group-label {
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 1rem;
  }
</style>
