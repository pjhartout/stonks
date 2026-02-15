<script lang="ts">
  import type { MetricSeries } from "../types";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";

  let { series, title }: { series: MetricSeries; title: string } = $props();

  let container: HTMLDivElement;
  let chart: uPlot | null = null;
  let ro: ResizeObserver | null = null;

  function makeData(data: MetricSeries): [Float64Array, Float64Array] {
    const steps = new Float64Array(data.steps);
    const values = new Float64Array(data.values.length);
    for (let i = 0; i < data.values.length; i++) {
      values[i] = data.values[i] ?? NaN;
    }
    return [steps, values];
  }

  function createChart(el: HTMLDivElement, data: MetricSeries) {
    const [steps, values] = makeData(data);

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: 200,
      cursor: { show: true, drag: { x: true, y: false } },
      legend: { show: false },
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
</style>
