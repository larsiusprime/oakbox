// First: in `npm run dev:wording` only, the live wording editor (empty in every other build).
import "./wording/edit/install";
// Then: timing each click to the screen settling (before anything keeps a reference to window.fetch).
import "./lib/perf";
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource-variable/ibm-plex-sans/wght-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import { WordingRoot } from "./wording";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});
// The Data wizard as it stands: every change to it hands back the new one (and what changes it elsewhere asks for it
// again), so a step showing it isn't a reason to read it again.
queryClient.setQueryDefaults(["wizard"], { staleTime: Number.POSITIVE_INFINITY });
// A field's histogram: keyed by its file, column and unit, so the same key is the same values; coming back to its
// step isn't a reason to read it again.
queryClient.setQueryDefaults(["histogram"], { staleTime: Number.POSITIVE_INFINITY });

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <WordingRoot>
        <App />
      </WordingRoot>
    </QueryClientProvider>
  </StrictMode>,
);
