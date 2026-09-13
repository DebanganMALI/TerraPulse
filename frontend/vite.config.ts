import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // /static is served by FastAPI outside /api/v1, so it needs its own proxy entry
    proxy: {
      "/static": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
});
