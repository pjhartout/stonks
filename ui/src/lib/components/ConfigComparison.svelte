<script lang="ts">
  import type { Run } from "../types";

  let { runs }: { runs: Run[] } = $props();

  let allKeys = $derived.by(() => {
    const keys = new Set<string>();
    for (const run of runs) {
      if (run.config) {
        for (const k of Object.keys(run.config)) {
          keys.add(k);
        }
      }
    }
    return Array.from(keys).sort();
  });
</script>

<div class="config-table">
  <h3>Config Comparison</h3>
  {#if runs.length === 0}
    <p class="empty">Select runs to compare configs.</p>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Parameter</th>
            {#each runs as run (run.id)}
              <th class="run-col">{run.name || run.id.slice(0, 8)}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each allKeys as key (key)}
            <tr>
              <td class="key">{key}</td>
              {#each runs as run (run.id)}
                <td class="val">{run.config?.[key] ?? "-"}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .config-table {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1rem;
  }
  h3 {
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
  }
  .empty {
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  th, td {
    padding: 0.4rem 0.6rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th {
    font-weight: 500;
    color: var(--text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .key {
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--accent);
  }
  .val {
    font-family: var(--font-mono);
    color: var(--text);
  }
  .run-col {
    font-family: var(--font-mono);
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
