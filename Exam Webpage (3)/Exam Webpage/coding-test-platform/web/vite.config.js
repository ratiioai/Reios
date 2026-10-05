import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Default: served by FastAPI at /app/. For a standalone deploy (e.g. Vercel) set
// VITE_BASE=/ and VITE_API_BASE=https://your-backend.example.com
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE || "/app/",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
