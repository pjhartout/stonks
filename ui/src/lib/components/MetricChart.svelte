<script lang="ts">
  import type { MetricSeries } from "../types";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";

  let { series, title }: { series: MetricSeries; title: string } = $props();

  let container: HTMLDivElement;
  let chart: uPlot | null = null;
  let ro: ResizeObserver | null = null;

  function fmtVal(v: number): string {
    if (Number.isNaN(v)) return "—";
    if (Number.isInteger(v)) return v.toString();
    if (Math.abs(v) >= 1) return v.toFixed(4);
    // small floats: show enough significant digits
    return v.toPrecision(4);
  }

  function makeData(data: MetricSeries): [Float64Array, Float64Array] {
    const steps = new Float64Array(data.steps);
    const values = new Float64Array(data.values.length);
    for (let i = 0; i < data.values.length; i++) {
      values[i] = data.values[i] ?? NaN;
    }
    return [steps, values];
  }

  function cursorTooltipPlugin(): uPlot.Plugin {
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
          const val = u.data[1][i] ?? NaN;
          tooltip.textContent = `Step ${step}  ·  ${fmtVal(val)}`;

          // Position tooltip near cursor, offset slightly
          const ttWidth = tooltip.offsetWidth;
          const plotWidth = over.clientWidth;
          // Flip to left side if near right edge
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

    return {
      hooks: {
        init: (u: uPlot) => {
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
          if (sel.width <= 0) {
            labelLeft.style.display = "none";
            labelRight.style.display = "none";
            return;
          }

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

  function createChart(el: HTMLDivElement, data: MetricSeries) {
    const [steps, values] = makeData(data);

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: 200,
      cursor: { show: true, drag: { x: true, y: false } },
      legend: { show: false },
      plugins: [cursorTooltipPlugin(), selectionRangePlugin()],
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
      series: [
        { label: "Step" },
        {
          label: data.key,
          stroke: "#6366f1",
          width: 1.5,
          fill: "#6366f120",
        },
      ],
    };

    chart = new uPlot(opts, [steps, values], el);

    // Resize chart when container width changes
    ro = new ResizeObserver((entries) => {
      if (chart) {
        const w = entries[0].contentRect.width;
        if (w > 0) chart.setSize({ width: w, height: 200 });
      }
    });
    ro.observe(el);
  }

  $effect(() => {
    if (!container || !series || series.steps.length === 0) return;

    if (chart) {
      const [steps, values] = makeData(series);
      chart.setData([steps, values]);
    } else {
      createChart(container, series);
    }

    return () => {
      ro?.disconnect();
      ro = null;
      if (chart) {
        chart.destroy();
        chart = null;
      }
    };
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
    padding: 3px 8px;
    font-size: 0.75rem;
    font-family: var(--font-mono, monospace);
    background: var(--bg-surface, #1e1e2e);
    color: var(--text-primary, #cdd6f4);
    border: 1px solid var(--border, #45475a);
    border-radius: 4px;
    white-space: nowrap;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
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
</style>
