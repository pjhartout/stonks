<script lang="ts">
  import type { RunSeries } from "../types";
  import { mergeRunSeries } from "../utils/merge";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";

  let { runs, title }: { runs: RunSeries[]; title: string } = $props();

  let container: HTMLDivElement;
  let chart: uPlot | null = null;
  let ro: ResizeObserver | null = null;
  let lastRunCount = 0;

  function fmtVal(v: number): string {
    if (Number.isNaN(v)) return "\u2014";
    if (Number.isInteger(v)) return v.toString();
    if (Math.abs(v) >= 1) return v.toFixed(4);
    return v.toPrecision(4);
  }

  function cursorTooltipPlugin(runSeries: RunSeries[]): uPlot.Plugin {
    let tooltip: HTMLDivElement;
    let over: HTMLElement;

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
          for (let s = 1; s < u.data.length; s++) {
            const val = u.data[s][i] ?? NaN;
            if (Number.isNaN(val)) continue;
            const run = runSeries[s - 1];
            const color = run?.color ?? "#888";
            const name = run?.runName ?? `Run ${s}`;
            html += `<div class="tt-row"><span class="tt-swatch" style="background:${color}"></span>${name}: ${fmtVal(val)}</div>`;
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

  function createChart(el: HTMLDivElement, runSeries: RunSeries[]) {
    const data = mergeRunSeries(runSeries);

    const seriesConfig: uPlot.Series[] = [
      { label: "Step" },
      ...runSeries.map((r) => ({
        label: r.runName,
        stroke: r.color,
        width: 1.5,
        fill: r.color + "20",
      })),
    ];

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: 200,
      cursor: { show: true, drag: { x: true, y: false } },
      legend: { show: runSeries.length > 1 },
      plugins: [cursorTooltipPlugin(runSeries), selectionRangePlugin()],
      scales: {
        x: { time: false },
      },
      axes: [
        {
          stroke: "#5c6078",
          grid: { stroke: "#2e334822" },
          ticks: { stroke: "#2e334822" },
          font: "11px Inter, sans-serif",
          labelFont: "11px Inter, sans-serif",
        },
        {
          stroke: "#5c6078",
          grid: { stroke: "#2e334844" },
          ticks: { stroke: "#2e334822" },
          font: "11px Inter, sans-serif",
          labelFont: "11px Inter, sans-serif",
          size: 60,
        },
      ],
      series: seriesConfig,
    };

    chart = new uPlot(opts, data, el);

    ro = new ResizeObserver((entries) => {
      if (chart) {
        const w = entries[0].contentRect.width;
        if (w > 0) chart.setSize({ width: w, height: 200 });
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

  // Update data or recreate chart when runs change
  $effect(() => {
    if (!container || !runs || runs.length === 0) return;

    // If the number of runs changed, we must recreate (uPlot series config is immutable)
    if (chart && runs.length === lastRunCount) {
      const data = mergeRunSeries(runs);
      chart.setData(data);
    } else {
      // Destroy old chart if exists
      if (chart) {
        ro?.disconnect();
        ro = null;
        chart.destroy();
        chart = null;
      }
      createChart(container, runs);
      lastRunCount = runs.length;
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
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
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
    background: rgba(99, 102, 241, 0.15) !important;
    border-left: 1px solid rgba(99, 102, 241, 0.6);
    border-right: 1px solid rgba(99, 102, 241, 0.6);
  }

  /* Dim overlay for areas outside selection */
  .chart-container :global(.sel-dim) {
    position: absolute;
    z-index: 1;
    pointer-events: none;
    background: rgba(0, 0, 0, 0.35);
  }
</style>
