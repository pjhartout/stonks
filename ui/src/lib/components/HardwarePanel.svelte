<script lang="ts">
  import type { MetricSeries, RunSeries } from "../types";
  import MetricChart from "./MetricChart.svelte";

  let { metrics, runName }: { metrics: Map<string, MetricSeries>; runName: string } = $props();

  let collapsed = $state(false);

  const subGroups: [string, string[]][] = [
    ["CPU / RAM", ["sys/cpu_percent", "sys/ram_used_gb", "sys/ram_total_gb", "sys/ram_percent"]],
    ["Disk I/O", ["sys/disk_read_mb", "sys/disk_write_mb"]],
    ["Network", ["sys/net_sent_mb", "sys/net_recv_mb"]],
  ];

  let gpuKeys = $derived.by(() => {
    const keys: string[] = [];
    for (const k of metrics.keys()) {
      if (k.startsWith("sys/gpu")) keys.push(k);
    }
    keys.sort();
    return keys;
  });

  /** Build the final list of sub-groups, appending GPU if present. */
  let visibleGroups = $derived.by(() => {
    const groups: [string, string[]][] = [];
    for (const [label, keys] of subGroups) {
      const present = keys.filter((k) => metrics.has(k));
      if (present.length > 0) groups.push([label, present]);
    }
    if (gpuKeys.length > 0) groups.push(["GPU", gpuKeys]);
    return groups;
  });

  /** Wrap a single MetricSeries into a RunSeries[] for MetricChart. */
  function wrapSeries(series: MetricSeries): RunSeries[] {
    return [{ runId: "hw", runName, color: "#6366f1", data: series }];
  }
</script>

{#if metrics.size > 0}
  <section class="hw-panel">
    <button class="hw-header" onclick={() => (collapsed = !collapsed)}>
      <span class="hw-chevron" class:rotated={!collapsed}>&#9654;</span>
      <h3>System Resources</h3>
      <span class="hw-badge">{metrics.size} metrics</span>
    </button>

    {#if !collapsed}
      <div class="hw-body">
        {#each visibleGroups as [label, keys] (label)}
          <div class="hw-subgroup">
            <h4 class="hw-subgroup-label">{label}</h4>
            <div class="charts-grid">
              {#each keys as key (key)}
                {#if metrics.has(key)}
                  <MetricChart runs={wrapSeries(metrics.get(key)!)} title={key} />
                {/if}
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </section>
{/if}

<style>
  .hw-panel {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }
  .hw-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.75rem 1rem;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-primary);
    text-align: left;
  }
  .hw-header:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.03));
  }
  .hw-chevron {
    font-size: 0.6rem;
    transition: transform 0.15s ease;
    color: var(--text-muted);
  }
  .hw-chevron.rotated {
    transform: rotate(90deg);
  }
  .hw-header h3 {
    font-size: 0.85rem;
    font-weight: 600;
    margin: 0;
  }
  .hw-badge {
    margin-left: auto;
    font-size: 0.7rem;
    color: var(--text-muted);
    background: var(--bg-badge, rgba(255, 255, 255, 0.06));
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
  }
  .hw-body {
    padding: 0 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .hw-subgroup {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .hw-subgroup-label {
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin: 0;
  }
  .charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 1rem;
  }
</style>
