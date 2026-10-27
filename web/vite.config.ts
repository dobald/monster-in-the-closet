import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend runs on :8000; the dev server proxies /api to it so the
// app and API share an origin (no CORS, cutout URLs work as-is).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
