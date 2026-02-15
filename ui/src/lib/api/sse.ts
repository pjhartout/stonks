import type { MetricsUpdateEvent, RunUpdateEvent } from "../types";

export type SSECallback = {
  onRunUpdate?: (event: RunUpdateEvent) => void;
  onMetricsUpdate?: (event: MetricsUpdateEvent) => void;
};

export function connectSSE(experimentId: string, callbacks: SSECallback): () => void {
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let aborted = false;
  let retryDelay = 1000;
  const MAX_DELAY = 30000;

  function connect() {
    if (aborted) return;
    source = new EventSource(`/api/events?experiment_id=${experimentId}`);

    source.addEventListener("run_update", (e: MessageEvent) => {
      const data: RunUpdateEvent = JSON.parse(e.data);
      callbacks.onRunUpdate?.(data);
    });

    source.addEventListener("metrics_update", (e: MessageEvent) => {
      const data: MetricsUpdateEvent = JSON.parse(e.data);
      callbacks.onMetricsUpdate?.(data);
    });

    source.onopen = () => {
      retryDelay = 1000;
    };

    source.onerror = () => {
      source?.close();
      source = null;
      if (!aborted) {
        reconnectTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
      }
    };
  }

  connect();

  return () => {
    aborted = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    source?.close();
    source = null;
  };
}
