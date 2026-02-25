<script lang="ts">
  import type { Run } from "../types";
  import { colorForRun, MAX_SELECTED_RUNS } from "../utils/colors";
  import ColorPicker from "./ColorPicker.svelte";
  import EmptyState from "./EmptyState.svelte";

  let {
    runs,
    selectedIds,
    primaryId,
    colorOverrides,
    onSelect,
    onToggle,
    onRename,
    onColorChange,
  }: {
    runs: Run[];
    selectedIds: Set<string>;
    primaryId: string | null;
    colorOverrides: Map<string, string>;
    onSelect: (id: string) => void;
    onToggle: (id: string) => void;
    onRename: (id: string, name: string) => void;
    onColorChange: (id: string, color: string) => void;
  } = $props();

  let editingRunId = $state<string | null>(null);
  let editValue = $state("");
  let editInput = $state<HTMLInputElement | null>(null);

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

  function startEditing(e: Event, run: Run) {
    e.stopPropagation();
    editingRunId = run.id;
    editValue = run.name || "";
    // Focus the input after Svelte renders it
    requestAnimationFrame(() => editInput?.focus());
  }

  function commitRename() {
    if (editingRunId) {
      onRename(editingRunId, editValue.trim());
      editingRunId = null;
    }
  }

  function cancelRename() {
    editingRunId = null;
  }

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitRename();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelRename();
    }
  }

  let colorPickerRunId = $state<string | null>(null);
  let pickerEl = $state<HTMLDivElement | null>(null);
  let swatchRefs = $state<Record<string, HTMLButtonElement | null>>({});

  function toggleColorPicker(e: Event, runId: string) {
    e.stopPropagation();
    e.preventDefault();
    if (colorPickerRunId === runId) {
      colorPickerRunId = null;
    } else {
      colorPickerRunId = runId;
    }
  }

  function handleDocumentClick(e: MouseEvent) {
    if (!colorPickerRunId) return;
    // If click is inside the picker wrapper, ignore
    if (pickerEl && pickerEl.contains(e.target as Node)) return;
    colorPickerRunId = null;
  }

  $effect(() => {
    if (colorPickerRunId) {
      // Defer to avoid catching the opening click
      requestAnimationFrame(() => {
        document.addEventListener("click", handleDocumentClick);
      });
      return () => {
        document.removeEventListener("click", handleDocumentClick);
      };
    }
  });
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
          <th class="th-color"></th>
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
            <td class="td-color">
              <button
                bind:this={swatchRefs[run.id]}
                class="color-swatch"
                style="background: {colorForRun(run.id, colorOverrides)}"
                onclick={(e) => toggleColorPicker(e, run.id)}
                title="Change run color"
              ></button>
              {#if colorPickerRunId === run.id && swatchRefs[run.id]}
                <div bind:this={pickerEl}>
                  <ColorPicker
                    value={colorForRun(run.id, colorOverrides)}
                    anchor={swatchRefs[run.id]!}
                    onChange={(c) => onColorChange(run.id, c)}
                  />
                </div>
              {/if}
            </td>
            <td>
              <span
                class="status-dot"
                style="background: {STATUS_COLORS[run.status] || 'var(--text-dim)'}"
                title={run.status}
              ></span>
            </td>
            <td class="name">
              {#if editingRunId === run.id}
                <input
                  bind:this={editInput}
                  class="name-input"
                  type="text"
                  bind:value={editValue}
                  onblur={commitRename}
                  onkeydown={handleRenameKeydown}
                  onclick={(e) => e.stopPropagation()}
                  placeholder={run.id.slice(0, 8)}
                />
              {:else}
                <span
                  class="name-text"
                  role="button"
                  tabindex="0"
                  ondblclick={(e) => startEditing(e, run)}
                  title="Double-click to rename"
                >{run.name || run.id.slice(0, 8)}</span>
              {/if}
            </td>
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
  .th-color {
    width: 28px;
    padding: 0.5rem 0.25rem;
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
  .td-color {
    width: 28px;
    padding: 0.5rem 0.25rem;
    position: relative;
  }
  .color-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    cursor: pointer;
    padding: 0;
  }
  .color-swatch:hover {
    border-color: rgba(255, 255, 255, 0.4);
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
  .name-text {
    cursor: text;
  }
  .name-text:hover {
    text-decoration: underline;
    text-decoration-style: dotted;
    text-underline-offset: 2px;
  }
  .name-input {
    background: var(--bg-base, #11111b);
    color: var(--text-primary);
    border: 1px solid var(--accent);
    border-radius: 3px;
    padding: 0.15rem 0.35rem;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    width: 14ch;
    outline: none;
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
