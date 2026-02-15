<script lang="ts">
  import { onMount } from "svelte";
  import ExperimentList from "./lib/components/ExperimentList.svelte";
  import RunTable from "./lib/components/RunTable.svelte";
  import MetricChart from "./lib/components/MetricChart.svelte";
  import ConfigComparison from "./lib/components/ConfigComparison.svelte";
  import EmptyState from "./lib/components/EmptyState.svelte";
  import {
    getExperiments,
    getSelectedExperimentId,
    getRuns,
    getSelectedRunId,
    getMetricKeys,
    getMetricData,
    getLoading,
    getError,
    loadExperiments,
    selectExperiment,
    selectRun,
    cleanup,
  } from "./lib/stores/experiments.svelte";

  onMount(() => {
    loadExperiments();
    return cleanup;
  });

  let experiments = $derived(getExperiments());
  let selectedExperimentId = $derived(getSelectedExperimentId());
  let runs = $derived(getRuns());
  let selectedRunId = $derived(getSelectedRunId());
  let metricKeys = $derived(getMetricKeys());
  let metricData = $derived(getMetricData());
  let loading = $derived(getLoading());
  let error = $derived(getError());

  let selectedRun = $derived(runs.find((r) => r.id === selectedRunId) ?? null);

  /** Group metric keys by prefix (e.g. train/loss -> train). */
  let groupedKeys = $derived.by(() => {
    const groups = new Map<string, string[]>();
    for (const key of metricKeys) {
      const slash = key.indexOf("/");
      const group = slash > 0 ? key.slice(0, slash) : "metrics";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)!.push(key);
    }
    return groups;
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
            selectedId={selectedRunId}
            onSelect={selectRun}
          />
        </section>

        {#if selectedRun}
          <section class="metrics-section">
            <h2>Metrics &mdash; {selectedRun.name || selectedRun.id.slice(0, 8)}</h2>

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
                      {#if metricData.has(key)}
                        <MetricChart
                          series={metricData.get(key)!}
                          title={key}
                        />
                      {/if}
                    {/each}
                  </div>
                </div>
              {/each}

              <ConfigComparison runs={[selectedRun]} />
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
