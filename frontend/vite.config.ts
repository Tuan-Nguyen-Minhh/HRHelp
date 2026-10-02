import { fileURLToPath, URL } from "node:url";
import type { ServerResponse } from "node:http";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", (_error, _req, res) => {
            const response = res as ServerResponse;
            if (response.headersSent) return;
            response.writeHead(502, { "Content-Type": "application/json" });
            response.end(JSON.stringify({ detail: "Không thể kết nối API. Hãy kiểm tra backend ở cổng 8000." }));
          });
        },
      },
    },
  },
});
