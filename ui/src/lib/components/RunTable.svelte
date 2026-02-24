<script lang="ts">
  import type { Run } from "../types";
  import { MAX_SELECTED_RUNS } from "../utils/colors";
  import EmptyState from "./EmptyState.svelte";

  let {
    runs,
    selectedIds,
    primaryId,
    onSelect,
    onToggle,
  }: {
    runs: Run[];
    selectedIds: Set<string>;
    primaryId: string | null;
    onSelect: (id: string) => void;
    onToggle: (id: string) => void;
  } = $props();

  const STATUS_COLORS: Record<Run["status"], string> = {
    running: "var(--yellow)",
    completed: "var(--green)",
    failed: "var(--red)",
    interrupted: "var(--orange)",
  };

  function formatDuration(run: Run): string {
    if (!run.ended_at) return "running...";
    const secs = Math.round(run.ended_at - run.created_at);
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
    return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
  }

  function configSummary(config: Record<string, unknown> | null): string {
    if (!config) return "";
    const entries = Object.entries(config).slice(0, 3);
    const parts = entries.map(([k, v]) => `${k}=${v}`);
    if (Object.keys(config).length > 3) parts.push("...");
    return parts.join(", ");
  }

  function formatTime(ts: number): string {
    return new Date(ts * 1000).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function handleCheckbox(e: Event, runId: string) {
    e.stopPropagation();
    onToggle(runId);
  }
</script>

<div class="run-table">
  {#if runs.length === 0}
    <EmptyState title="No runs" message="Runs will appear here when training starts." />
  {:else}
    {#if selectedIds.size > 0}
      <div class="selection-info">
        {selectedIds.size} of {runs.length} run{runs.length !== 1 ? "s" : ""} selected
        {#if selectedIds.size >= MAX_SELECTED_RUNS}
          <span class="limit-badge">max</span>
        {/if}
      </div>
    {/if}
    <table>
      <thead>
        <tr>
          <th class="th-checkbox"></th>
          <th>Status</th>
          <th>Name</th>
          <th>Duration</th>
          <th>Config</th>
          <th>Started</th>
        </tr>
      </thead>
      <tbody>
        {#each runs as run (run.id)}
          <tr
            class:selected={selectedIds.has(run.id)}
            class:primary={primaryId === run.id}
            onclick={() => onSelect(run.id)}
          >
            <td class="td-checkbox">
              <input
                type="checkbox"
                checked={selectedIds.has(run.id)}
                disabled={!selectedIds.has(run.id) && selectedIds.size >= MAX_SELECTED_RUNS}
                onclick={(e) => handleCheckbox(e, run.id)}
                title={!selectedIds.has(run.id) && selectedIds.size >= MAX_SELECTED_RUNS
                  ? `Maximum ${MAX_SELECTED_RUNS} runs can be compared`
                  : "Toggle comparison"}
              />
            </td>
            <td>
              <span
                class="status-dot"
                style="background: {STATUS_COLORS[run.status] || 'var(--text-dim)'}"
                title={run.status}
              ></span>
            </td>
            <td class="name">{run.name || run.id.slice(0, 8)}</td>
            <td class="duration">{formatDuration(run)}</td>
            <td class="config">{configSummary(run.config)}</td>
            <td class="time">{formatTime(run.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .run-table {
    overflow-x: auto;
  }
  .selection-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.75rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
  }
  .limit-badge {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--orange);
    background: rgba(249, 115, 22, 0.1);
    padding: 0.1rem 0.4rem;
    border-radius: 999px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  thead {
    position: sticky;
    top: 0;
    background: var(--bg-surface);
    z-index: 1;
  }
  th {
    text-align: left;
    padding: 0.5rem 0.75rem;
    font-weight: 500;
    color: var(--text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border);
  }
  .th-checkbox {
    width: 32px;
    padding: 0.5rem 0.5rem;
  }
  td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  .td-checkbox {
    width: 32px;
    padding: 0.5rem 0.5rem;
  }
  .td-checkbox input[type="checkbox"] {
    cursor: pointer;
    accent-color: var(--accent);
  }
  .td-checkbox input[type="checkbox"]:disabled {
    cursor: not-allowed;
    opacity: 0.4;
  }
  tr {
    cursor: pointer;
  }
  tr:hover td {
    background: var(--bg-hover);
  }
  tr.selected td {
    background: var(--bg-active);
  }
  tr.primary td {
    border-left: 2px solid var(--accent);
  }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .name {
    font-weight: 500;
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }
  .duration {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }
  .config {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .time {
    color: var(--text-dim);
    font-size: 0.8rem;
  }
</style>
