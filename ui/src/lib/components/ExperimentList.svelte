<script lang="ts">
  import type { Experiment } from "../types";
  import EmptyState from "./EmptyState.svelte";

  let {
    experiments,
    selectedId,
    onSelect,
  }: {
    experiments: Experiment[];
    selectedId: string | null;
    onSelect: (id: string) => void;
  } = $props();

  function formatDate(ts: number): string {
    return new Date(ts * 1000).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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
        <li>
          <button
            class="item"
            class:active={selectedId === exp.id}
            onclick={() => onSelect(exp.id)}
          >
            <span class="name">{exp.name}</span>
            <span class="meta">
              {exp.run_count} run{exp.run_count !== 1 ? "s" : ""}
              &middot;
              {formatDate(exp.created_at)}
            </span>
          </button>
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
  .item {
    display: flex;
    flex-direction: column;
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: none;
    background: none;
    color: var(--text);
    text-align: left;
    cursor: pointer;
    border-radius: var(--radius);
    gap: 0.15rem;
    font-family: inherit;
    font-size: inherit;
  }
  .item:hover {
    background: var(--bg-hover);
  }
  .item.active {
    background: var(--bg-active);
    border-left: 2px solid var(--accent);
  }
  .name {
    font-weight: 500;
    font-size: 0.9rem;
  }
  .meta {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
</style>
