<script lang="ts">
  let {
    value,
    anchor,
    onChange,
  }: {
    value: string;
    anchor: HTMLElement;
    onChange: (color: string) => void;
  } = $props();

  let cpEl: HTMLDivElement | null = $state(null);
  let posStyle = $state("");

  $effect(() => {
    if (!anchor || !cpEl) return;
    const rect = anchor.getBoundingClientRect();
    const pickerHeight = cpEl.offsetHeight || 160;
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow >= pickerHeight + 8) {
      posStyle = `top: ${rect.bottom + 4}px; left: ${rect.left}px;`;
    } else {
      posStyle = `top: ${rect.top - pickerHeight - 4}px; left: ${rect.left}px;`;
    }
  });

  const SWATCHES = [
    "#6366f1", "#818cf8", "#a78bfa", "#8b5cf6",
    "#ec4899", "#f43f5e", "#ef4444", "#f97316",
    "#eab308", "#22c55e", "#10b981", "#14b8a6",
    "#06b6d4", "#0ea5e9", "#3b82f6", "#6d28d9",
    "#78716c", "#a1a1aa", "#d4d4d8", "#f5f5f4",
  ];

  function applyHex(input: HTMLInputElement) {
    let v = input.value.trim();
    if (!v.startsWith("#")) v = "#" + v;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) {
      onChange(v);
    }
  }
</script>

<div class="cp" bind:this={cpEl} style={posStyle} onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
  <div class="cp-grid">
    {#each SWATCHES as color (color)}
      <button
        class="cp-swatch"
        class:active={value === color}
        style="background: {color}"
        onclick={() => onChange(color)}
        title={color}
      ></button>
    {/each}
  </div>
  <div class="cp-hex">
    <div class="cp-preview" style="background: {value}"></div>
    <input
      class="cp-input"
      type="text"
      value={value}
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") applyHex(e.currentTarget as HTMLInputElement);
      }}
      onblur={(e) => applyHex(e.currentTarget as HTMLInputElement)}
    />
  </div>
</div>

<style>
  .cp {
    position: fixed;
    z-index: 20;
    padding: 8px;
    background: var(--bg-surface, #1e1e2e);
    border: 1px solid var(--border, #45475a);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
    width: 172px;
    user-select: none;
  }
  .cp-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    margin-bottom: 6px;
  }
  .cp-swatch {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 4px;
    border: 2px solid transparent;
    cursor: pointer;
    padding: 0;
  }
  .cp-swatch:hover {
    border-color: rgba(255, 255, 255, 0.4);
  }
  .cp-swatch.active {
    border-color: white;
  }
  .cp-hex {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cp-preview {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    flex-shrink: 0;
  }
  .cp-input {
    flex: 1;
    font-size: 0.7rem;
    font-family: var(--font-mono, monospace);
    color: var(--text-primary, #cdd6f4);
    background: var(--bg-base, #11111b);
    border: 1px solid var(--border, #45475a);
    border-radius: 3px;
    padding: 2px 6px;
    outline: none;
    min-width: 0;
  }
  .cp-input:focus {
    border-color: var(--accent, #6366f1);
  }
</style>
