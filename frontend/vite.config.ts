import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", sourcemap: false },
  server: { proxy: { "/v1": "http://127.0.0.1:8080", "/health": "http://127.0.0.1:8080" } },
});
