import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { copyEdit } from "./scripts/copy-edit-plugin.mjs";

// The built UI is served by the Python app service (src/oakbox/app.py).
// In development, `npm run dev` proxies /api to a running `python -m oakbox --no-window --port 8765`.
// `npm run dev:copy` is the same with the live copy editor (SPEC §6.6): only that mode compiles it in.
export default defineConfig(({ mode }) => ({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] }), ...(mode === "copyedit" ? [copyEdit()] : [])],
  define: { __COPY_EDIT__: JSON.stringify(mode === "copyedit") },
  // MapLibre's worker is a module (it imports MapLibre's shared code): bundled as one, an ES module.
  worker: { format: "es" },
  build: {
    outDir: "../src/oakbox/web",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
}));
