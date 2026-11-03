import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The built UI is served by the Python app service (src/oakbox/app.py).
// In development, `npm run dev` proxies /api to a running `python -m oakbox --no-window --port 8765`.
export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  // MapLibre's worker is a module (it imports MapLibre's shared code): bundled as one, an ES module.
  worker: { format: "es" },
  build: {
    outDir: "../src/oakbox/web",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
