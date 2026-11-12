import { describe, expect, it } from "vitest";
import { EDGE_FULL_PX, EDGE_NONE_PX, edgeShare } from "./detail";

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
