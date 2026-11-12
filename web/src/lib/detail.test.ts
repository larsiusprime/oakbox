import { describe, expect, it } from "vitest";
import { DETAILS, EDGE_FULL_PX, EDGE_NONE_PX, edgeShare, LOT_M, shapesAt } from "./detail";

describe("edgeShare", () => {
  it("draws no edges while parcels are a few pixels across, and full ones once they're big", () => {
    expect(edgeShare(40, 40 / (EDGE_NONE_PX - 1))).toBe(0);
    expect(edgeShare(40, 40 / EDGE_FULL_PX)).toBe(1);
    expect(edgeShare(40, 40 / 100)).toBe(1);
    const mid = edgeShare(40, 40 / ((EDGE_NONE_PX + EDGE_FULL_PX) / 2));
    expect(mid).toBeGreaterThan(0.4);
    expect(mid).toBeLessThan(0.6);
  });
  it("draws edges when the size or zoom isn't known yet", () => {
    expect(edgeShare(null, 10)).toBe(1);
    expect(edgeShare(40, null)).toBe(1);
  });
});

describe("shapesAt", () => {
  // Metres a pixel covers where a quarter-acre lot is this many pixels across.
  const at = (px: number) => LOT_M / px;
  it("draws parcels at every zoom on Max", () => {
    expect(shapesAt("max", 10_000)).toBe(true);
  });
  it("tiles out at a quarter-acre lot 2, 8, 16 and 32 pixels across", () => {
    for (const [d, px] of [
      ["high", 1],
      ["medium", 8],
      ["low", 16],
      ["verylow", 32],
    ] as const) {
      expect(shapesAt(d, at(px * 1.01))).toBe(true);
      expect(shapesAt(d, at(px * 0.99))).toBe(false);
    }
  });
  it("draws parcels at some zoom on every level, fewer the lower it is", () => {
    for (const d of DETAILS) expect(shapesAt(d, 0.1)).toBe(true);
    const shown = (mpp: number) => DETAILS.filter((d) => shapesAt(d, mpp)).length;
    expect(shown(at(4))).toBe(2);
    expect(shown(at(1.5))).toBe(2);
    expect(shown(at(0.5))).toBe(1);
    expect(shown(at(12))).toBe(3);
  });
});
