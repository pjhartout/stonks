<script lang="ts">
  import type { Run, StatusFilter } from "../types";

  let {
    runs,
    statusFilter,
    tagFilters,
    searchQuery,
    onStatusChange,
    onTagToggle,
    onTagRemove,
    onSearchChange,
    onClearAll,
  }: {
    runs: Run[];
    statusFilter: StatusFilter;
    tagFilters: Set<string>;
    searchQuery: string;
    onStatusChange: (status: StatusFilter) => void;
    onTagToggle: (tag: string) => void;
    onTagRemove: (tag: string) => void;
    onSearchChange: (query: string) => void;
    onClearAll: () => void;
  } = $props();

  // Collect all unique tags across runs
  let allTags = $derived.by(() => {
    const tags = new Set<string>();
    for (const run of runs) {
      if (run.tags) {
        for (const tag of run.tags) {
          tags.add(tag);
        }
      }
    }
    return [...tags].sort();
  });

  let hasActiveFilters = $derived(
    statusFilter !== "all" || tagFilters.size > 0 || searchQuery.length > 0,
  );

  let showTagDropdown = $state(false);
  let tagDropdownEl = $state<HTMLDivElement | null>(null);

  function handleTagDropdownOutsideClick(e: MouseEvent) {
    if (tagDropdownEl && !tagDropdownEl.contains(e.target as Node)) {
      showTagDropdown = false;
    }
  }

  $effect(() => {
    if (showTagDropdown) {
      requestAnimationFrame(() => {
        document.addEventListener("click", handleTagDropdownOutsideClick);
      });
      return () => {
        document.removeEventListener("click", handleTagDropdownOutsideClick);
      };
    }
  });
</script>

<div class="filter-bar">
  <div class="filter-controls">
    <select
      class="status-select"
      value={statusFilter}
      onchange={(e) => onStatusChange((e.target as HTMLSelectElement).value as StatusFilter)}
    >
      <option value="all">All statuses</option>
      <option value="running">Running</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
      <option value="interrupted">Interrupted</option>
    </select>

    {#if allTags.length > 0}
      <div class="tag-dropdown-wrap" bind:this={tagDropdownEl}>
        <button
          class="tag-dropdown-btn"
          onclick={(e) => {
            e.stopPropagation();
            showTagDropdown = !showTagDropdown;
          }}
        >
          Tags
          {#if tagFilters.size > 0}
            <span class="tag-count">{tagFilters.size}</span>
          {/if}
          <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none" />
          </svg>
        </button>
        {#if showTagDropdown}
          <div class="tag-dropdown">
            {#each allTags as tag}
              <label class="tag-option">
                <input
                  type="checkbox"
                  checked={tagFilters.has(tag)}
                  onchange={() => onTagToggle(tag)}
                />
                {tag}
              </label>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <input
      class="search-input"
      type="text"
      placeholder="Search runs..."
      value={searchQuery}
      oninput={(e) => onSearchChange((e.target as HTMLInputElement).value)}
    />

    {#if hasActiveFilters}
      <button class="clear-btn" onclick={onClearAll}>Clear filters</button>
    {/if}
  </div>

  {#if hasActiveFilters}
    <div class="active-filters">
      {#if statusFilter !== "all"}
        <span class="active-chip">
          {statusFilter}
          <button class="chip-dismiss" onclick={() => onStatusChange("all")}>&times;</button>
        </span>
      {/if}
      {#each [...tagFilters] as tag}
        <span class="active-chip tag-active-chip">
          {tag}
          <button class="chip-dismiss" onclick={() => onTagRemove(tag)}>&times;</button>
        </span>
      {/each}
      {#if searchQuery.length > 0}
        <span class="active-chip">
          &ldquo;{searchQuery}&rdquo;
          <button class="chip-dismiss" onclick={() => onSearchChange("")}>&times;</button>
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .filter-bar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .filter-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .status-select {
    background: var(--bg-surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
    outline: none;
    font-family: inherit;
  }
  .status-select:hover {
    border-color: var(--text-dim);
  }
  .status-select:focus {
    border-color: var(--accent);
  }
  .tag-dropdown-wrap {
    position: relative;
  }
  .tag-dropdown-btn {
    background: var(--bg-surface);
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-family: inherit;
  }
  .tag-dropdown-btn:hover {
    color: var(--text);
    border-color: var(--text-dim);
  }
  .tag-count {
    background: var(--accent);
    color: white;
    font-size: 0.65rem;
    padding: 0 0.35rem;
    border-radius: 999px;
    min-width: 16px;
    text-align: center;
  }
  .tag-dropdown {
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 4px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0;
    z-index: 10;
    min-width: 160px;
    max-height: 200px;
    overflow-y: auto;
  }
  .tag-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
    color: var(--text);
    cursor: pointer;
    font-family: var(--font-mono);
  }
  .tag-option:hover {
    background: var(--bg-hover);
  }
  .tag-option input[type="checkbox"] {
    accent-color: var(--accent);
  }
  .search-input {
    background: var(--bg-surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0.6rem;
    font-size: 0.8rem;
    outline: none;
    min-width: 160px;
    font-family: inherit;
  }
  .search-input::placeholder {
    color: var(--text-dim);
  }
  .search-input:focus {
    border-color: var(--accent);
  }
  .clear-btn {
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.35rem 0.5rem;
    font-family: inherit;
  }
  .clear-btn:hover {
    color: var(--text-muted);
  }
  .active-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .active-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.15rem 0.5rem;
    font-size: 0.7rem;
    background: var(--bg-active);
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 999px;
  }
  .tag-active-chip {
    background: rgba(99, 102, 241, 0.15);
    color: var(--accent-hover);
    border-color: rgba(99, 102, 241, 0.3);
    font-family: var(--font-mono);
  }
  .chip-dismiss {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    font-size: 0.85rem;
    padding: 0;
    line-height: 1;
    opacity: 0.6;
  }
  .chip-dismiss:hover {
    opacity: 1;
  }
</style>
