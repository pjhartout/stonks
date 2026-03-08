<script lang="ts">
  import type { Run } from "../types";
  import { colorForRun, MAX_SELECTED_RUNS } from "../utils/colors";
  import ColorPicker from "./ColorPicker.svelte";
  import EmptyState from "./EmptyState.svelte";

  const VISIBLE_COLS_KEY = "stonks:visible-columns";

  let {
    runs,
    selectedIds,
    primaryId,
    colorOverrides,
    onSelect,
    onToggle,
    onRename,
    onColorChange,
    onTagFilter,
    onDeleteRun,
    onUpdateNotes,
  }: {
    runs: Run[];
    selectedIds: Set<string>;
    primaryId: string | null;
    colorOverrides: Map<string, string>;
    onSelect: (id: string) => void;
    onToggle: (id: string) => void;
    onRename: (id: string, name: string) => void;
    onColorChange: (id: string, color: string) => void;
    onTagFilter?: (tag: string) => void;
    onDeleteRun?: (id: string) => void;
    onUpdateNotes?: (id: string, notes: string) => void;
  } = $props();

  let editingRunId = $state<string | null>(null);
  let editValue = $state("");
  let editInput = $state<HTMLInputElement | null>(null);

  // Notes inline editing state
  let editingNotesRunId = $state<string | null>(null);
  let notesEditValue = $state("");
  let notesEditInput = $state<HTMLInputElement | null>(null);

  // Column visibility
  type OptionalColumn = "group" | "job_type";
  let visibleOptionalCols = $state<Set<OptionalColumn>>(loadVisibleColumns());
  let showColumnMenu = $state(false);

  function loadVisibleColumns(): Set<OptionalColumn> {
    try {
      const raw = localStorage.getItem(VISIBLE_COLS_KEY);
      if (raw) return new Set(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    return new Set();
  }

  function saveVisibleColumns() {
    localStorage.setItem(VISIBLE_COLS_KEY, JSON.stringify([...visibleOptionalCols]));
  }

  function toggleColumn(col: OptionalColumn) {
    const next = new Set(visibleOptionalCols);
    if (next.has(col)) {
      next.delete(col);
    } else {
      next.add(col);
    }
    visibleOptionalCols = next;
    saveVisibleColumns();
  }

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

  // Notes editing
  function startEditingNotes(e: Event, run: Run) {
    e.stopPropagation();
    editingNotesRunId = run.id;
    notesEditValue = run.notes || "";
    requestAnimationFrame(() => notesEditInput?.focus());
  }

  function commitNotes() {
    if (editingNotesRunId && onUpdateNotes) {
      onUpdateNotes(editingNotesRunId, notesEditValue.trim());
      editingNotesRunId = null;
    }
  }

  function cancelNotes() {
    editingNotesRunId = null;
  }

  function handleNotesKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitNotes();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelNotes();
    }
  }

  function handleTagClick(e: Event, tag: string) {
    e.stopPropagation();
    onTagFilter?.(tag);
  }

  // Delete confirmation
  let confirmDeleteRunId = $state<string | null>(null);

  function handleDeleteClick(e: Event, runId: string) {
    e.stopPropagation();
    confirmDeleteRunId = runId;
  }

  function confirmDelete(e: Event) {
    e.stopPropagation();
    if (confirmDeleteRunId) {
      onDeleteRun?.(confirmDeleteRunId);
      confirmDeleteRunId = null;
    }
  }

  function cancelDelete(e: Event) {
    e.stopPropagation();
    confirmDeleteRunId = null;
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
    if (pickerEl && pickerEl.contains(e.target as Node)) return;
    colorPickerRunId = null;
  }

  $effect(() => {
    if (colorPickerRunId) {
      requestAnimationFrame(() => {
        document.addEventListener("click", handleDocumentClick);
      });
      return () => {
        document.removeEventListener("click", handleDocumentClick);
      };
    }
  });

  // Close column menu on outside click
  let columnMenuEl = $state<HTMLDivElement | null>(null);

  function handleColumnMenuOutsideClick(e: MouseEvent) {
    if (columnMenuEl && !columnMenuEl.contains(e.target as Node)) {
      showColumnMenu = false;
    }
  }

  $effect(() => {
    if (showColumnMenu) {
      requestAnimationFrame(() => {
        document.addEventListener("click", handleColumnMenuOutsideClick);
      });
      return () => {
        document.removeEventListener("click", handleColumnMenuOutsideClick);
      };
    }
  });
</script>

<div class="run-table">
  {#if runs.length === 0}
    <EmptyState title="No runs" message="Runs will appear here when training starts." />
  {:else}
    <div class="table-toolbar">
      {#if selectedIds.size > 0}
        <div class="selection-info">
          {selectedIds.size} of {runs.length} run{runs.length !== 1 ? "s" : ""} selected
          {#if selectedIds.size >= MAX_SELECTED_RUNS}
            <span class="limit-badge">max</span>
          {/if}
        </div>
      {/if}
      <div class="toolbar-right" bind:this={columnMenuEl}>
        <button
          class="col-toggle-btn"
          onclick={(e) => {
            e.stopPropagation();
            showColumnMenu = !showColumnMenu;
          }}
          title="Toggle columns"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
            <path d="M1 2h4v12H1V2zm5 0h4v12H6V2zm5 0h4v12h-4V2z" opacity="0.7" />
          </svg>
        </button>
        {#if showColumnMenu}
          <div class="col-menu">
            <label class="col-menu-item">
              <input
                type="checkbox"
                checked={visibleOptionalCols.has("group")}
                onchange={() => toggleColumn("group")}
              />
              Group
            </label>
            <label class="col-menu-item">
              <input
                type="checkbox"
                checked={visibleOptionalCols.has("job_type")}
                onchange={() => toggleColumn("job_type")}
              />
              Job Type
            </label>
          </div>
        {/if}
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th class="th-checkbox"></th>
          <th class="th-color"></th>
          <th>Status</th>
          <th>Name</th>
          <th>Tags</th>
          {#if visibleOptionalCols.has("group")}
            <th>Group</th>
          {/if}
          {#if visibleOptionalCols.has("job_type")}
            <th>Job Type</th>
          {/if}
          <th>Duration</th>
          <th>Config</th>
          <th>Started</th>
          <th class="th-notes">Notes</th>
          <th class="th-actions"></th>
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
            <td class="tags-cell">
              {#if run.tags && run.tags.length > 0}
                <div class="tag-chips">
                  {#each run.tags as tag}
                    <button
                      class="tag-chip"
                      onclick={(e) => handleTagClick(e, tag)}
                      title="Filter by tag: {tag}"
                    >{tag}</button>
                  {/each}
                </div>
              {/if}
            </td>
            {#if visibleOptionalCols.has("group")}
              <td class="optional-col">{run.group ?? "\u2014"}</td>
            {/if}
            {#if visibleOptionalCols.has("job_type")}
              <td class="optional-col">{run.job_type ?? "\u2014"}</td>
            {/if}
            <td class="duration">{formatDuration(run)}</td>
            <td class="config">{configSummary(run.config)}</td>
            <td class="time">{formatTime(run.created_at)}</td>
            <td class="notes-cell">
              {#if editingNotesRunId === run.id}
                <input
                  bind:this={notesEditInput}
                  class="notes-input"
                  type="text"
                  bind:value={notesEditValue}
                  onblur={commitNotes}
                  onkeydown={handleNotesKeydown}
                  onclick={(e) => e.stopPropagation()}
                  placeholder="Add notes..."
                />
              {:else}
                <span
                  class="notes-text"
                  role="button"
                  tabindex="0"
                  ondblclick={(e) => startEditingNotes(e, run)}
                  title={run.notes || "Double-click to add notes"}
                >{run.notes ? (run.notes.length > 30 ? run.notes.slice(0, 30) + "\u2026" : run.notes) : ""}</span>
              {/if}
            </td>
            <td class="td-actions">
              {#if confirmDeleteRunId === run.id}
                <span class="confirm-delete">
                  <button class="btn-confirm-yes" onclick={(e) => confirmDelete(e)} title="Confirm delete">Yes</button>
                  <button class="btn-confirm-no" onclick={(e) => cancelDelete(e)} title="Cancel">No</button>
                </span>
              {:else}
                <button
                  class="btn-delete"
                  onclick={(e) => handleDeleteClick(e, run.id)}
                  title="Delete run"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                    <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4L4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
                  </svg>
                </button>
              {/if}
            </td>
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
  .table-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4rem 0.75rem;
    border-bottom: 1px solid var(--border);
    min-height: 32px;
  }
  .toolbar-right {
    position: relative;
    margin-left: auto;
  }
  .col-toggle-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 0.25rem 0.4rem;
    border-radius: var(--radius);
    cursor: pointer;
    display: flex;
    align-items: center;
  }
  .col-toggle-btn:hover {
    color: var(--text);
    border-color: var(--text-dim);
  }
  .col-menu {
    position: absolute;
    right: 0;
    top: 100%;
    margin-top: 4px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0;
    z-index: 10;
    min-width: 140px;
  }
  .col-menu-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
    color: var(--text);
    cursor: pointer;
    white-space: nowrap;
  }
  .col-menu-item:hover {
    background: var(--bg-hover);
  }
  .col-menu-item input[type="checkbox"] {
    accent-color: var(--accent);
  }
  .selection-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-muted);
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
  .th-notes {
    width: 120px;
  }
  .th-actions {
    width: 40px;
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
    border: 1px solid var(--swatch-border, rgba(255, 255, 255, 0.15));
    cursor: pointer;
    padding: 0;
  }
  .color-swatch:hover {
    border-color: var(--swatch-border-hover, rgba(255, 255, 255, 0.4));
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
  .tags-cell {
    white-space: normal;
    max-width: 200px;
  }
  .tag-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .tag-chip {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    font-size: 0.7rem;
    font-family: var(--font-mono);
    background: rgba(99, 102, 241, 0.15);
    color: var(--accent-hover);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 999px;
    cursor: pointer;
    white-space: nowrap;
    line-height: 1.4;
  }
  .tag-chip:hover {
    background: rgba(99, 102, 241, 0.25);
    border-color: var(--accent);
  }
  .optional-col {
    color: var(--text-muted);
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
  .notes-cell {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .notes-text {
    color: var(--text-dim);
    font-size: 0.75rem;
    cursor: text;
  }
  .notes-text:hover {
    color: var(--text-muted);
  }
  .notes-input {
    background: var(--bg-base, #11111b);
    color: var(--text);
    border: 1px solid var(--accent);
    border-radius: 3px;
    padding: 0.15rem 0.35rem;
    font-size: 0.75rem;
    width: 100%;
    outline: none;
  }
  .td-actions {
    width: 40px;
    padding: 0.5rem 0.25rem;
  }
  .btn-delete {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    padding: 0.15rem;
    border-radius: 3px;
    display: flex;
    align-items: center;
    opacity: 0;
    transition: opacity 0.1s;
  }
  tr:hover .btn-delete {
    opacity: 1;
  }
  .btn-delete:hover {
    color: var(--red);
    background: rgba(239, 68, 68, 0.1);
  }
  .confirm-delete {
    display: flex;
    gap: 0.25rem;
  }
  .btn-confirm-yes,
  .btn-confirm-no {
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    border: none;
    cursor: pointer;
    font-weight: 500;
  }
  .btn-confirm-yes {
    background: var(--red);
    color: white;
  }
  .btn-confirm-yes:hover {
    opacity: 0.9;
  }
  .btn-confirm-no {
    background: var(--bg-hover);
    color: var(--text-muted);
  }
  .btn-confirm-no:hover {
    background: var(--bg-active);
  }
</style>
