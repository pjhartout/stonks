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
    const pickerHeight = cpEl.offsetHeight || 200;
    const spaceBelow = window.innerHeight - rect.bottom;
    // Open below if there's room, otherwise above
    if (spaceBelow >= pickerHeight + 8) {
      posStyle = `top: ${rect.bottom + 4}px; left: ${rect.left}px;`;
    } else {
      posStyle = `top: ${rect.top - pickerHeight - 4}px; left: ${rect.left}px;`;
    }
  });

  // Parse initial hex to HSL
  let hue = $state(0);
  let sat = $state(100);
  let light = $state(50);

  let draggingHue = $state(false);
  let draggingSL = $state(false);

  let hueBar: HTMLDivElement | null = $state(null);
  let slPad: HTMLDivElement | null = $state(null);

  function hexToHsl(hex: string): [number, number, number] {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    if (max === min) return [0, 0, Math.round(l * 100)];
    const d = max - min;
    const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    let h = 0;
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
    return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
  }

  function hslToHex(h: number, s: number, l: number): string {
    const sl = s / 100;
    const ll = l / 100;
    const c = (1 - Math.abs(2 * ll - 1)) * sl;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = ll - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) { r = c; g = x; }
    else if (h < 120) { r = x; g = c; }
    else if (h < 180) { g = c; b = x; }
    else if (h < 240) { g = x; b = c; }
    else if (h < 300) { r = x; b = c; }
    else { r = c; b = x; }
    const toHex = (v: number) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  }

  // Init from prop
  $effect(() => {
    if (value && !draggingHue && !draggingSL) {
      [hue, sat, light] = hexToHsl(value);
    }
  });

  function emit() {
    onChange(hslToHex(hue, sat, light));
  }

  // Hue bar handlers
  function updateHue(clientX: number) {
    if (!hueBar) return;
    const rect = hueBar.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    hue = Math.round((x / rect.width) * 360);
    emit();
  }

  function onHueDown(e: PointerEvent) {
    e.stopPropagation();
    e.preventDefault();
    draggingHue = true;
    updateHue(e.clientX);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onHueMove(e: PointerEvent) {
    if (!draggingHue) return;
    updateHue(e.clientX);
  }

  function onHueUp() {
    draggingHue = false;
  }

  // SL pad handlers
  function updateSL(clientX: number, clientY: number) {
    if (!slPad) return;
    const rect = slPad.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const y = Math.max(0, Math.min(clientY - rect.top, rect.height));
    sat = Math.round((x / rect.width) * 100);
    light = Math.round((1 - y / rect.height) * 100);
    emit();
  }

  function onSLDown(e: PointerEvent) {
    e.stopPropagation();
    e.preventDefault();
    draggingSL = true;
    updateSL(e.clientX, e.clientY);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onSLMove(e: PointerEvent) {
    if (!draggingSL) return;
    updateSL(e.clientX, e.clientY);
  }

  function onSLUp() {
    draggingSL = false;
  }
</script>

<div class="cp" bind:this={cpEl} style={posStyle} onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
  <div
    class="cp-sl"
    role="slider"
    tabindex="0"
    aria-label="Saturation and lightness"
    aria-valuemin={0}
    aria-valuemax={100}
    aria-valuenow={sat}
    bind:this={slPad}
    style="background: linear-gradient(to right, hsl({hue}, 0%, 50%), hsl({hue}, 100%, 50%))"
    onpointerdown={onSLDown}
    onpointermove={onSLMove}
    onpointerup={onSLUp}
  >
    <div class="cp-sl-white"></div>
    <div class="cp-sl-black"></div>
    <div
      class="cp-sl-thumb"
      style="left: {sat}%; top: {100 - light}%"
    ></div>
  </div>

  <div
    class="cp-hue"
    role="slider"
    tabindex="0"
    aria-label="Hue"
    aria-valuemin={0}
    aria-valuemax={360}
    aria-valuenow={hue}
    bind:this={hueBar}
    onpointerdown={onHueDown}
    onpointermove={onHueMove}
    onpointerup={onHueUp}
  >
    <div class="cp-hue-thumb" style="left: {(hue / 360) * 100}%"></div>
  </div>

  <div class="cp-preview">
    <div class="cp-preview-swatch" style="background: {hslToHex(hue, sat, light)}"></div>
    <input
      class="cp-hex-input"
      type="text"
      value={hslToHex(hue, sat, light)}
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
          const input = e.currentTarget as HTMLInputElement;
          let v = input.value.trim();
          if (!v.startsWith("#")) v = "#" + v;
          if (/^#[0-9a-fA-F]{6}$/.test(v)) {
            [hue, sat, light] = hexToHsl(v);
            emit();
          }
        }
      }}
      onblur={(e) => {
        const input = e.currentTarget as HTMLInputElement;
        let v = input.value.trim();
        if (!v.startsWith("#")) v = "#" + v;
        if (/^#[0-9a-fA-F]{6}$/.test(v)) {
          [hue, sat, light] = hexToHsl(v);
          emit();
        }
      }}
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
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 180px;
    user-select: none;
    touch-action: none;
  }

  .cp-sl {
    position: relative;
    width: 100%;
    height: 120px;
    border-radius: 4px;
    cursor: crosshair;
    touch-action: none;
  }
  .cp-sl-white {
    position: absolute;
    inset: 0;
    border-radius: 4px;
    background: linear-gradient(to bottom, white, transparent);
  }
  .cp-sl-black {
    position: absolute;
    inset: 0;
    border-radius: 4px;
    background: linear-gradient(to top, black, transparent);
  }
  .cp-sl-thumb {
    position: absolute;
    width: 12px;
    height: 12px;
    border: 2px solid white;
    border-radius: 50%;
    box-shadow: 0 0 2px rgba(0, 0, 0, 0.6);
    transform: translate(-50%, -50%);
    pointer-events: none;
  }

  .cp-hue {
    position: relative;
    width: 100%;
    height: 14px;
    border-radius: 7px;
    background: linear-gradient(
      to right,
      hsl(0, 100%, 50%),
      hsl(60, 100%, 50%),
      hsl(120, 100%, 50%),
      hsl(180, 100%, 50%),
      hsl(240, 100%, 50%),
      hsl(300, 100%, 50%),
      hsl(360, 100%, 50%)
    );
    cursor: pointer;
    touch-action: none;
  }
  .cp-hue-thumb {
    position: absolute;
    top: 50%;
    width: 10px;
    height: 14px;
    border: 2px solid white;
    border-radius: 3px;
    box-shadow: 0 0 2px rgba(0, 0, 0, 0.6);
    transform: translate(-50%, -50%);
    pointer-events: none;
  }

  .cp-preview {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cp-preview-swatch {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    flex-shrink: 0;
  }
  .cp-hex-input {
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
  .cp-hex-input:focus {
    border-color: var(--accent, #6366f1);
  }
</style>
