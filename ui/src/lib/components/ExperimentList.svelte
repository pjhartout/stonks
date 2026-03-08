<script lang="ts">
  import type { Experiment } from "../types";
  import EmptyState from "./EmptyState.svelte";

  let {
    experiments,
    selectedId,
    onSelect,
    onDelete,
  }: {
    experiments: Experiment[];
    selectedId: string | null;
    onSelect: (id: string) => void;
    onDelete?: (id: string) => void;
  } = $props();

  let confirmDeleteId = $state<string | null>(null);

  function formatDate(ts: number): string {
    return new Date(ts * 1000).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function handleDeleteClick(e: Event, id: string) {
    e.stopPropagation();
    confirmDeleteId = id;
  }

  function confirmDelete(e: Event) {
    e.stopPropagation();
    if (confirmDeleteId) {
      onDelete?.(confirmDeleteId);
      confirmDeleteId = null;
    }
  }

  function cancelDelete(e: Event) {
    e.stopPropagation();
    confirmDeleteId = null;
  }
</script>

<nav class="sidebar">
  <div class="header">
    <h1>stonks</h1>
  </div>

  {#if experiments.length === 0}
    <EmptyState title="No experiments" message="Start logging to see experiments here." />
  {:else}
    <ul class="list">
      {#each experiments as exp (exp.id)}
        <li class="item-wrapper" class:active={selectedId === exp.id}>
          <button
            class="item"
            onclick={() => onSelect(exp.id)}
          >
            <span class="name">{exp.name}</span>
            <span class="meta">
              {exp.run_count} run{exp.run_count !== 1 ? "s" : ""}
              &middot;
              {formatDate(exp.created_at)}
            </span>
          </button>
          {#if confirmDeleteId === exp.id}
            <span class="confirm-delete">
              <button class="btn-confirm-yes" onclick={(e) => confirmDelete(e)} title="Delete experiment and all runs">Yes</button>
              <button class="btn-confirm-no" onclick={(e) => cancelDelete(e)} title="Cancel">No</button>
            </span>
          {:else if onDelete}
            <button
              class="btn-delete-exp"
              onclick={(e) => handleDeleteClick(e, exp.id)}
              title="Delete experiment"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4L4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
              </svg>
            </button>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</nav>

<style>
  .sidebar {
    width: 260px;
    min-width: 260px;
    height: 100%;
    border-right: 1px solid var(--border);
    background: var(--bg-surface);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .header {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border);
  }
  h1 {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--accent);
  }
  .list {
    list-style: none;
    overflow-y: auto;
    flex: 1;
    padding: 0.5rem;
  }
  .item-wrapper {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0 0.75rem;
    border-radius: var(--radius);
    cursor: pointer;
  }
  .item-wrapper:hover {
    background: var(--bg-hover);
  }
  .item-wrapper.active {
    background: var(--bg-active);
    border-left: 2px solid var(--accent);
  }
  .item {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    padding: 0.6rem 0;
    border: none;
    background: none;
    color: var(--text);
    text-align: left;
    cursor: pointer;
    gap: 0.15rem;
    font-family: inherit;
    font-size: inherit;
  }
  .name {
    font-weight: 500;
    font-size: 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .btn-delete-exp {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    padding: 0.1rem;
    border-radius: 3px;
    display: flex;
    align-items: center;
    opacity: 0;
    transition: opacity 0.1s;
    flex-shrink: 0;
  }
  .item-wrapper:hover .btn-delete-exp {
    opacity: 1;
  }
  .btn-delete-exp:hover {
    color: var(--red);
    background: rgba(239, 68, 68, 0.1);
  }
  .confirm-delete {
    display: flex;
    gap: 0.2rem;
    flex-shrink: 0;
  }
  .btn-confirm-yes,
  .btn-confirm-no {
    font-size: 0.6rem;
    padding: 0.1rem 0.3rem;
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
