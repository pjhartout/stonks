<script lang="ts">
  import { onMount } from "svelte";
  import ExperimentList from "./lib/components/ExperimentList.svelte";
  import FilterBar from "./lib/components/FilterBar.svelte";
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
    getFilteredRuns,
    getSelectedRunIds,
    getPrimaryRunId,
    getMetricKeys,
    getMetricData,
    getColorOverrides,
    getLoading,
    getError,
    getStatusFilter,
    getTagFilters,
    getSearchQuery,
    loadExperiments,
    selectExperiment,
    selectRun,
    toggleRunSelection,
    setRunColor,
    renameRun,
    updateRunNotes,
    deleteRun,
    deleteExperiment,
    setStatusFilter,
    toggleTagFilter,
    removeTagFilter,
    setSearchQuery,
    clearAllFilters,
    syncToUrl,
    restoreFromUrl,
    cleanup,
  } from "./lib/stores/experiments.svelte";

  const THEME_KEY = "stonks:theme";

  function getInitialTheme(): "dark" | "light" {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: light)").matches) {
      return "light";
    }
    return "dark";
  }

  let theme = $state<"dark" | "light">(getInitialTheme());

  function toggleTheme() {
    theme = theme === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, theme);
  }

  // Apply theme class to document root
  $effect(() => {
    if (theme === "light") {
      document.documentElement.classList.add("light");
    } else {
      document.documentElement.classList.remove("light");
    }
  });

  let isDark = $derived(theme === "dark");

  let initialized = $state(false);

  onMount(() => {
    loadExperiments().then(() => restoreFromUrl()).then(() => { initialized = true; });
    return cleanup;
  });

  // Sync selection state to URL whenever it changes (after initial load).
  // selectedExperimentId and selectedRunIds are read here so Svelte tracks
  // them as dependencies of this effect; removing these reads will break the
  // URL sync.
  $effect(() => {
    if (!initialized) return;
    const expId = selectedExperimentId;
    const runIds = [...selectedRunIds];
    void `${expId}|${runIds.join(",")}`;
    syncToUrl();
  });

  let experiments = $derived(getExperiments());
  let selectedExperimentId = $derived(getSelectedExperimentId());
  let allRuns = $derived(getRuns());
  let filteredRuns = $derived(getFilteredRuns());
  let selectedRunIds = $derived(getSelectedRunIds());
  let primaryRunId = $derived(getPrimaryRunId());
  let metricKeys = $derived(getMetricKeys());
  let metricData = $derived(getMetricData());
  let colorOverrides = $derived(getColorOverrides());
  let loading = $derived(getLoading());
  let error = $derived(getError());
  let statusFilter = $derived(getStatusFilter());
  let tagFilters = $derived(getTagFilters());
  let searchQuery = $derived(getSearchQuery());

  let selectedRuns = $derived(filteredRuns.filter((r) => selectedRunIds.has(r.id)));

  /** Separate hardware (sys/) keys from training keys. */
  let trainingKeys = $derived(metricKeys.filter((k) => !k.startsWith("sys/")));
  let hardwareKeys = $derived(metricKeys.filter((k) => k.startsWith("sys/")));

  /** Build RunSeries[] for a set of metric keys across selected runs. */
  function buildSeriesMap(keys: string[]): Map<string, RunSeries[]> {
    const map = new Map<string, RunSeries[]>();
    for (const key of keys) {
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
  }

  let hardwareByKey = $derived(buildSeriesMap(hardwareKeys));

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

  let runsByKey = $derived(buildSeriesMap(trainingKeys));

  /** Header text for the metrics section. */
  let metricsHeader = $derived.by(() => {
    if (selectedRuns.length === 0) return "";
    if (selectedRuns.length === 1) {
      const r = selectedRuns[0];
      return `Metrics \u2014 ${r.name || r.id.slice(0, 8)}`;
    }
    return `Comparing ${selectedRuns.length} runs`;
  });

  type Tab = "runs" | "metrics" | "hardware";
  let activeTab = $state<Tab>("runs");

  // Auto-switch to metrics tab when a run is first selected
  let prevSelectedCount = $state(0);
  $effect(() => {
    const count = selectedRuns.length;
    if (count > 0 && prevSelectedCount === 0) {
      activeTab = "metrics";
    }
    prevSelectedCount = count;
  });

  let hasHardware = $derived(hardwareByKey.size > 0);

  function handleTagFilter(tag: string) {
    toggleTagFilter(tag);
  }
</script>

<div class="app">
  <ExperimentList
    {experiments}
    selectedId={selectedExperimentId}
    onSelect={selectExperiment}
    onDelete={deleteExperiment}
    {isDark}
    onToggleTheme={toggleTheme}
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
        <nav class="tabs">
          <button
            class="tab"
            class:active={activeTab === "runs"}
            onclick={() => activeTab = "runs"}
          >
            Runs
            <span class="tab-count">{filteredRuns.length}</span>
          </button>
          <button
            class="tab"
            class:active={activeTab === "metrics"}
            onclick={() => activeTab = "metrics"}
            disabled={selectedRuns.length === 0}
          >
            Metrics
            {#if trainingKeys.length > 0}
              <span class="tab-count">{trainingKeys.length}</span>
            {/if}
          </button>
          {#if hasHardware}
            <button
              class="tab"
              class:active={activeTab === "hardware"}
              onclick={() => activeTab = "hardware"}
              disabled={selectedRuns.length === 0}
            >
              Hardware
              <span class="tab-count">{hardwareKeys.length}</span>
            </button>
          {/if}
          {#if selectedRuns.length > 0}
            <span class="tab-info">{metricsHeader}</span>
          {/if}
        </nav>

        {#if activeTab === "runs"}
          <section class="tab-content">
            <FilterBar
              runs={allRuns}
              {statusFilter}
              {tagFilters}
              {searchQuery}
              onStatusChange={setStatusFilter}
              onTagToggle={toggleTagFilter}
              onTagRemove={removeTagFilter}
              onSearchChange={setSearchQuery}
              onClearAll={clearAllFilters}
            />
            <RunTable
              runs={filteredRuns}
              selectedIds={selectedRunIds}
              primaryId={primaryRunId}
              {colorOverrides}
              onSelect={selectRun}
              onToggle={toggleRunSelection}
              onRename={renameRun}
              onColorChange={setRunColor}
              onTagFilter={handleTagFilter}
              onDeleteRun={deleteRun}
              onUpdateNotes={updateRunNotes}
            />
          </section>
        {:else if activeTab === "metrics"}
          <section class="tab-content">
            {#if selectedRuns.length === 0}
              <EmptyState
                title="No runs selected"
                message="Select a run from the Runs tab to view its metrics."
              />
            {:else if trainingKeys.length === 0}
              <EmptyState
                title="No metrics"
                message="This run has no logged training metrics yet."
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
        {:else if activeTab === "hardware"}
          <section class="tab-content">
            {#if selectedRuns.length === 0}
              <EmptyState
                title="No runs selected"
                message="Select a run from the Runs tab to view hardware metrics."
              />
            {:else}
              <HardwarePanel metricsByKey={hardwareByKey} />
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
    gap: 1rem;
  }
  .tabs {
    display: flex;
    align-items: center;
    gap: 0;
    border-bottom: 1px solid var(--border);
  }
  .tab {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.6rem 1rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab:hover:not(:disabled) {
    color: var(--text);
  }
  .tab:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .tab.active {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  .tab-count {
    font-size: 0.7rem;
    background: var(--bg-hover);
    color: var(--text-dim);
    padding: 0.1rem 0.4rem;
    border-radius: 999px;
    font-weight: 400;
  }
  .tab.active .tab-count {
    background: rgba(99, 102, 241, 0.15);
    color: var(--accent);
  }
  .tab-info {
    margin-left: auto;
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .tab-content {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
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
