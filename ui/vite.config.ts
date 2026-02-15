import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: resolve(__dirname, "../stonks/server/static"),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/events": "http://127.0.0.1:8000",
    },
  },
});
