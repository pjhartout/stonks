<script lang="ts">
  import type { RunSeries } from "../types";
  import { mergeRunSeries, hasBands } from "../utils/merge";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";

  let { runs, title }: { runs: RunSeries[]; title: string } = $props();

  let container: HTMLDivElement;
  let chart: uPlot | null = null;
  let ro: ResizeObserver | null = null;
  let lastSeriesKey = "";
  let themeClass = $state(document.documentElement.classList.contains("light") ? "light" : "dark");

  // Watch for theme changes on <html> element
  $effect(() => {
    const observer = new MutationObserver(() => {
      const newTheme = document.documentElement.classList.contains("light") ? "light" : "dark";
      if (newTheme !== themeClass) {
        themeClass = newTheme;
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  });

  function escapeHtml(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /** Build a key that changes when series count or colors change (forces chart recreation). */
  function seriesKey(rs: RunSeries[]): string {
    return rs.map((r) => `${r.runId}:${r.color}`).join("|");
  }

  function fmtVal(v: number): string {
    if (Number.isNaN(v)) return "\u2014";
    if (Number.isInteger(v)) return v.toString();
    if (Math.abs(v) >= 1) return v.toFixed(4);
    return v.toPrecision(4);
  }

  /**
   * Build a mapping from data array index to the RunSeries it belongs to,
   * plus whether it's the mean/min/max series.
   */
  function buildSeriesIndexMap(runSeries: RunSeries[]): Map<number, { run: RunSeries; role: "mean" | "min" | "max" }> {
    const map = new Map<number, { run: RunSeries; role: "mean" | "min" | "max" }>();
    let idx = 1; // 0 is x-axis
    for (const r of runSeries) {
      map.set(idx, { run: r, role: "mean" });
      idx++;
      if (r.data.values_min && r.data.values_max) {
        map.set(idx, { run: r, role: "min" });
        map.set(idx + 1, { run: r, role: "max" });
        idx += 2;
      }
    }
    return map;
  }

  function cursorTooltipPlugin(runSeries: RunSeries[]): uPlot.Plugin {
    let tooltip: HTMLDivElement;
    let over: HTMLElement;
    const indexMap = buildSeriesIndexMap(runSeries);

    return {
      hooks: {
        init: (u: uPlot) => {
          over = u.over;

          tooltip = document.createElement("div");
          tooltip.className = "chart-tooltip";
          tooltip.style.display = "none";
          u.root.querySelector(".u-wrap")!.appendChild(tooltip);

          over.addEventListener("mouseenter", () => {
            tooltip.style.display = "block";
          });
          over.addEventListener("mouseleave", () => {
            tooltip.style.display = "none";
          });
        },
        setCursor: (u: uPlot) => {
          const { left, idx } = u.cursor;
          if (idx == null || left == null || left < 0) {
            tooltip.style.display = "none";
            return;
          }

          const i = idx as number;
          const step = u.data[0][i];
          let html = `<div class="tt-step">Step ${step}</div>`;

          // Show one tooltip row per run (mean value, plus spread if available)
          for (let s = 1; s < u.data.length; s++) {
            const info = indexMap.get(s);
            if (!info || info.role !== "mean") continue;
            const val = u.data[s][i] ?? NaN;
            if (Number.isNaN(val)) continue;
            const color = info.run.color;
            const name = info.run.runName;

            // Check if there's a min/max for this run
            const minInfo = indexMap.get(s + 1);
            const maxInfo = indexMap.get(s + 2);
            let spread = "";
            if (minInfo?.role === "min" && maxInfo?.role === "max") {
              const minVal = u.data[s + 1][i] ?? NaN;
              const maxVal = u.data[s + 2][i] ?? NaN;
              if (!Number.isNaN(minVal) && !Number.isNaN(maxVal)) {
                spread = ` <span class="tt-spread">[${fmtVal(minVal)} \u2013 ${fmtVal(maxVal)}]</span>`;
              }
            }

            html += `<div class="tt-row"><span class="tt-swatch" style="background:${escapeHtml(color)}"></span>${escapeHtml(name)}: ${fmtVal(val)}${spread}</div>`;
          }
          tooltip.innerHTML = html;

          const ttWidth = tooltip.offsetWidth;
          const plotWidth = over.clientWidth;
          if (left + 12 + ttWidth > plotWidth) {
            tooltip.style.left = `${left - ttWidth - 8}px`;
          } else {
            tooltip.style.left = `${left + 12}px`;
          }
          tooltip.style.top = "8px";
          tooltip.style.display = "block";
        },
      },
    };
  }

  function selectionRangePlugin(): uPlot.Plugin {
    let labelLeft: HTMLDivElement;
    let labelRight: HTMLDivElement;
    let dimLeft: HTMLDivElement;
    let dimRight: HTMLDivElement;

    return {
      hooks: {
        init: (u: uPlot) => {
          const over = u.over;

          dimLeft = document.createElement("div");
          dimLeft.className = "sel-dim";
          dimLeft.style.display = "none";
          dimLeft.style.left = "0";
          over.appendChild(dimLeft);

          dimRight = document.createElement("div");
          dimRight.className = "sel-dim";
          dimRight.style.display = "none";
          over.appendChild(dimRight);

          const wrap = u.root.querySelector(".u-wrap")!;

          labelLeft = document.createElement("div");
          labelLeft.className = "sel-label sel-label-left";
          labelLeft.style.display = "none";
          wrap.appendChild(labelLeft);

          labelRight = document.createElement("div");
          labelRight.className = "sel-label sel-label-right";
          labelRight.style.display = "none";
          wrap.appendChild(labelRight);
        },
        setSelect: (u: uPlot) => {
          const sel = u.select;
          const overWidth = u.over.clientWidth;
          const overHeight = u.over.clientHeight;

          if (sel.width <= 0) {
            labelLeft.style.display = "none";
            labelRight.style.display = "none";
            dimLeft.style.display = "none";
            dimRight.style.display = "none";
            return;
          }

          dimLeft.style.display = "block";
          dimLeft.style.width = `${sel.left}px`;
          dimLeft.style.height = `${overHeight}px`;
          dimLeft.style.top = "0";

          dimRight.style.display = "block";
          dimRight.style.left = `${sel.left + sel.width}px`;
          dimRight.style.width = `${overWidth - sel.left - sel.width}px`;
          dimRight.style.height = `${overHeight}px`;
          dimRight.style.top = "0";

          const leftVal = u.posToVal(sel.left, "x");
          const rightVal = u.posToVal(sel.left + sel.width, "x");

          labelLeft.textContent = `${Math.round(leftVal)}`;
          labelLeft.style.left = `${sel.left}px`;
          labelLeft.style.top = `${sel.top + sel.height + 2}px`;
          labelLeft.style.display = "block";

          labelRight.textContent = `${Math.round(rightVal)}`;
          labelRight.style.left = `${sel.left + sel.width}px`;
          labelRight.style.top = `${sel.top + sel.height + 2}px`;
          labelRight.style.display = "block";
        },
      },
    };
  }

  function readCssVar(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function hexToRgba(hex: string, alpha: number): string {
    const c = hex.replace("#", "");
    const r = parseInt(c.substring(0, 2), 16);
    const g = parseInt(c.substring(2, 4), 16);
    const b = parseInt(c.substring(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function createChart(el: HTMLDivElement, runSeries: RunSeries[]) {
    const data = mergeRunSeries(runSeries);
    const bands = hasBands(runSeries);

    const seriesConfig: uPlot.Series[] = [{ label: "Step" }];
    const uBands: uPlot.Band[] = [];

    // Track which data array index we're at
    let dataIdx = 1;
    for (const r of runSeries) {
      const meanIdx = dataIdx;
      // Mean line
      seriesConfig.push({
        label: r.runName,
        stroke: r.color,
        width: 1.5,
      });
      dataIdx++;

      if (r.data.values_min && r.data.values_max) {
        const minIdx = dataIdx;
        const maxIdx = dataIdx + 1;
        // Min series (hidden line, used only for band fill)
        seriesConfig.push({
          show: true,
          width: 0,
          stroke: "transparent",
          points: { show: false },
        } as uPlot.Series);
        // Max series (hidden line, used only for band fill)
        seriesConfig.push({
          show: true,
          width: 0,
          stroke: "transparent",
          points: { show: false },
        } as uPlot.Series);
        // Band between min and max
        uBands.push({
          series: [maxIdx, minIdx],
          fill: hexToRgba(r.color, 0.15),
        });
        dataIdx += 2;
      }
    }

    const axisStroke = readCssVar("--chart-axis");
    const gridStroke = readCssVar("--chart-grid");
    const gridStrokeStrong = readCssVar("--chart-grid-strong");
    const axisFont = "11px Inter, sans-serif";

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: 300,
      cursor: { show: true, drag: { x: true, y: false } },
      legend: { show: runSeries.length > 1 },
      plugins: [cursorTooltipPlugin(runSeries), selectionRangePlugin()],
      scales: {
        x: { time: false },
      },
      bands: uBands.length > 0 ? uBands : undefined,
      axes: [
        {
          stroke: axisStroke,
          grid: { stroke: gridStroke },
          ticks: { stroke: gridStroke },
          font: axisFont,
          labelFont: axisFont,
        },
        {
          stroke: axisStroke,
          grid: { stroke: gridStrokeStrong },
          ticks: { stroke: gridStroke },
          font: axisFont,
          labelFont: axisFont,
          size: 60,
        },
      ],
      series: seriesConfig,
    };

    chart = new uPlot(opts, data, el);

    ro = new ResizeObserver((entries) => {
      if (chart) {
        const w = entries[0].contentRect.width;
        if (w > 0) chart.setSize({ width: w, height: 300 });
      }
    });
    ro.observe(el);
  }

  // Create chart once on mount, destroy on unmount
  $effect(() => {
    if (!container) return;

    return () => {
      ro?.disconnect();
      ro = null;
      if (chart) {
        chart.destroy();
        chart = null;
      }
    };
  });

  // Update data or recreate chart when runs or theme change
  $effect(() => {
    if (!container || !runs || runs.length === 0) return;

    // Include themeClass in the key so theme changes force chart recreation
    const key = `${seriesKey(runs)}|${themeClass}`;
    // Recreate if series count, colors, or theme changed (uPlot config is immutable)
    if (chart && key === lastSeriesKey) {
      const data = mergeRunSeries(runs);
      chart.setData(data);
    } else {
      if (chart) {
        ro?.disconnect();
        ro = null;
        chart.destroy();
        chart = null;
      }
      createChart(container, runs);
      lastSeriesKey = key;
    }
  });
</script>

<div class="chart-container">
  <h4>{title}</h4>
  <div class="chart" bind:this={container}></div>
</div>

<style>
  .chart-container {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1rem;
  }
  h4 {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
    font-family: var(--font-mono);
  }
  .chart {
    width: 100%;
  }

  /* Tooltip shown on hover */
  .chart-container :global(.chart-tooltip) {
    position: absolute;
    z-index: 10;
    pointer-events: none;
    padding: 6px 10px;
    font-size: 0.75rem;
    font-family: var(--font-mono, monospace);
    background: var(--bg-surface, #1e1e2e);
    color: var(--text-primary, #cdd6f4);
    border: 1px solid var(--border, #45475a);
    border-radius: 4px;
    white-space: nowrap;
    box-shadow: 0 2px 6px var(--shadow-tooltip, rgba(0, 0, 0, 0.3));
  }
  .chart-container :global(.tt-step) {
    margin-bottom: 2px;
    color: var(--text-muted, #a6adc8);
    font-size: 0.7rem;
  }
  .chart-container :global(.tt-row) {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .chart-container :global(.tt-swatch) {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  /* uPlot legend styling for multi-run */
  .chart-container :global(.u-legend) {
    font-size: 0.7rem;
    font-family: var(--font-mono, monospace);
    color: var(--text-muted, #a6adc8);
    padding: 4px 0 0;
  }
  .chart-container :global(.u-legend .u-series) {
    padding: 1px 6px;
  }
  .chart-container :global(.tt-spread) {
    color: var(--text-dim, #6c7086);
    font-size: 0.65rem;
  }

  /* Selection range labels */
  .chart-container :global(.sel-label) {
    position: absolute;
    z-index: 10;
    pointer-events: none;
    font-size: 0.65rem;
    font-family: var(--font-mono, monospace);
    color: var(--text-muted, #a6adc8);
    background: var(--bg-surface, #1e1e2e);
    padding: 1px 4px;
    border-radius: 2px;
    white-space: nowrap;
  }
  .chart-container :global(.sel-label-left) {
    transform: translateX(-100%);
  }
  .chart-container :global(.sel-label-right) {
    transform: translateX(0);
  }

  /* Make the selection box clearly visible */
  .chart-container :global(.u-select) {
    background: var(--chart-select, rgba(99, 102, 241, 0.15)) !important;
    border-left: 1px solid var(--chart-select-border, rgba(99, 102, 241, 0.6));
    border-right: 1px solid var(--chart-select-border, rgba(99, 102, 241, 0.6));
  }

  /* Dim overlay for areas outside selection */
  .chart-container :global(.sel-dim) {
    position: absolute;
    z-index: 1;
    pointer-events: none;
    background: var(--chart-dim, rgba(0, 0, 0, 0.35));
  }
</style>
