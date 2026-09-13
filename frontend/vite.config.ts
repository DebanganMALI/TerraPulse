import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 127.0.0.1 rather than localhost: on windows localhost resolves to ::1 first
// and uvicorn's default bind is ipv4 only
const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/static": { target: API, changeOrigin: true },
    },
  },
});
