/** This computer (SPEC §5): what the check found, the performance settings, and the graphics part of the check,
 * which only the page can do. */
import { Deck } from "@deck.gl/core";
import { SolidPolygonLayer } from "@deck.gl/layers";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type MachineView, type Performance, type Resolved, unwrap } from "../api/client";

export function useMachine() {
  return useQuery({
    queryKey: ["machine"],
    queryFn: async () => unwrap(await api.GET("/api/machine")),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** The performance settings as they come to on this computer; Standard's until the check has answered. */
export function useResolved(): Resolved {
  return (
    useMachine().data?.resolved ?? {
      fold_workers: "two",
      folds_at_once: 2,
      maps: "now",
      map_detail: "auto",
      street_map: "on",
    }
  );
}

export function useSetPerformance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Performance) => unwrap(await api.PUT("/api/performance", { body })),
    onSuccess: (view: MachineView) => queryClient.setQueryData(["machine"], view),
  });
}

/** Settings opens from anywhere (the plate's gear, File › Settings…, a map's note), at a section. */
export type SettingsSection = "performance" | "display" | "projects" | "keys";
const OPEN = "oakbox-settings";

export function openSettings(section: SettingsSection = "performance"): void {
  window.dispatchEvent(new CustomEvent(OPEN, { detail: section }));
}

export function onOpenSettings(handler: (section: SettingsSection) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<SettingsSection>).detail);
  window.addEventListener(OPEN, listener);
  return () => window.removeEventListener(OPEN, listener);
}

/** WebGL's renderer, as the graphics driver names it; null without WebGL. */
export function renderer(): string | null {
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl2") ?? canvas.getContext("webgl")) as WebGLRenderingContext | null;
    if (!gl) return null;
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    const name = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return typeof name === "string" && name ? name : null;
  } catch {
    return null;
  }
}

/** 20,000 small parcels drawn as a map draws them (deck.gl, off screen): how long until they're on screen, ms. */
export function drawTest(n = 20_000): Promise<number | null> {
  return new Promise((resolve) => {
    const canvas = document.createElement("canvas");
    canvas.style.cssText = "position:fixed;left:-10000px;top:0;width:800px;height:600px";
    document.body.appendChild(canvas);
    const side = Math.ceil(Math.sqrt(n));
    const d = 0.0004;
    const data = Array.from({ length: n }, (_, i) => {
      const x = -77.5 + (i % side) * d * 1.2;
      const y = 38.75 + Math.floor(i / side) * d * 1.2;
      return [
        [x, y],
        [x + d, y],
        [x + d, y + d],
        [x, y + d],
      ];
    });
    const t0 = performance.now();
    let deck: Deck | null = null;
    let done = false;
    const finish = (ms: number | null) => {
      if (done) return;
      done = true;
      window.setTimeout(() => {
        deck?.finalize();
        canvas.remove();
      }, 0);
      resolve(ms);
    };
    const timer = window.setTimeout(() => finish(null), 20_000);
    try {
      deck = new Deck({
        canvas,
        width: 800,
        height: 600,
        initialViewState: {
          longitude: -77.5 + (side * d * 1.2) / 2,
          latitude: 38.75 + (side * d * 1.2) / 2,
          zoom: 13,
        },
        controller: false,
        layers: [
          new SolidPolygonLayer({
            id: "test",
            data,
            getPolygon: (p) => p,
            getFillColor: [80, 120, 200, 180],
          }),
        ],
        onAfterRender: () => {
          // The first frame with the layer drawn. WebGL only queues the drawing: reading a pixel back waits for it
          // to be done, as the screen would.
          const gl = (canvas.getContext("webgl2") ?? canvas.getContext("webgl")) as WebGLRenderingContext | null;
          gl?.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
          window.clearTimeout(timer);
          finish(Math.round(performance.now() - t0));
        },
        onError: () => finish(null),
      });
    } catch {
      window.clearTimeout(timer);
      finish(null);
    }
  });
}
