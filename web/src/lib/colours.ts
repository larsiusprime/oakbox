/** Colours that mean something, shared by the screens that draw them: in SVG and on maps (deck.gl), where the
 * stylesheet's tokens don't reach. Where one is a token too, it says which. */

/** A chart's parts (SVG). */
export const CHART = {
  bar: "#7fa3d9", // --chart-bar
  axis: "#888888",
  label: "#555555",
  mark: "#333333", // a line marking a value (a median)
  ink: "#222222",
  grid: "#e2e4e6", // --cell-line
  band: "#e7f5ec", // --ok-tint: the range a ratio should be in
};

/** A sale trimmed from the ratio study (an outlier): on its map, in its chart and their keys. */
export const TRIMMED = { fill: "#d0d0d0", line: "#9a9a9a" };

/** A sale on Across prices' chart. */
export const BY_SALE = "#d4566f";

/** What's picked or found on a map (--link). */
export const PICKED = "#1d5bb8";
/** A boundary that's wrong on a map (--bad). */
export const BAD = "#a3231b";
/** Outliers' map: a sale valued under its price (--under, the ratio maps' blue below 1), over it (--over, their red),
 * within the band (grey); the sale picked, ringed, and its comps' outlines. */
export const OUTLIER = {
  under: "#2f5d9b",
  over: "#b3362e",
  within: "#9a9a9a",
  ring: CHART.ink,
  comp: CHART.mark,
};
/** A model group with no colour of its own. */
export const NO_COLOUR = "#9a9a9a";
/** On a sale's chart: the sale itself, others set aside too, and the rest. */
export const SALE = { self: "#dd3333", flagged: "#e8955a", other: CHART.bar };

/** openratiostudy.com's colours: blue below 1 (deepest at 0.5), white at 1, red above (deepest at 2). */
export function ratioColor(q: number): string {
  if (!Number.isFinite(q)) return "#94a3b8";
  if (q <= 1) {
    const c = Math.round(255 * Math.max(0, Math.min(1, (q - 0.5) / 0.5)));
    return `rgb(${c}, ${c}, 255)`;
  }
  const c = Math.round(255 * (1 - Math.max(0, Math.min(1, q - 1))));
  return `rgb(255, ${c}, ${c})`;
}

export function ratioStroke(q: number): string {
  return q < 0.9 ? "#1d4ed8" : q > 1.1 ? "#b91c1c" : "#475569";
}

/** openratiostudy.com's VEI chart (its Plotly colours): blue boxes, a red sample median, dark interval bars. */
export const ORS = {
  boxFill: "rgba(59,130,246,0.35)",
  boxLine: "#1d4ed8",
  boxMarker: "#3b82f6",
  boxDot: "#4285F4",
  median: "#dc2626",
  ci: "rgba(15,23,42,0.95)",
  ciDot: "#0f172a",
  grid: "#e2e8f0",
  ink: "#1f2937",
};
