import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "path";
import { defineConfig } from "vite";

const apiTarget = process.env.API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, "../stonks/server/static"),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api/events": {
        target: apiTarget,
        // SSE requires no response buffering and longer timeout
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            proxyRes.headers["cache-control"] = "no-cache";
            proxyRes.headers["x-accel-buffering"] = "no";
          });
        },
        timeout: 0,
      },
      "/api": apiTarget,
    },
  },
});
