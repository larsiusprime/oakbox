import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { wordingEdit } from "./scripts/wording-edit-plugin.mjs";

// The built UI is served by the Python app service (src/oakbox/app.py).
// In development, `npm run dev` proxies /api to a running `python -m oakbox --no-window --port 8765`.
// `npm run dev:wording` is the same with the live wording editor (SPEC §6.6): only that mode compiles it in.
export default defineConfig(({ mode }) => ({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] }), ...(mode === "wordingedit" ? [wordingEdit()] : [])],
  define: { __WORDING_EDIT__: JSON.stringify(mode === "wordingedit") },
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
