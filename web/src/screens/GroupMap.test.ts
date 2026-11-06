import { describe, expect, it } from "vitest";
import { shapeSize } from "./GroupMap";

// A square side `d` degrees wide with its corner at (x, y).
const square = (x: number, y: number, d: number): GeoJSON.Feature => ({
  type: "Feature",
  properties: {},
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [x, y],
        [x + d, y],
        [x + d, y + d],
        [x, y + d],
        [x, y],
      ],
    ],
  },
});
const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features,
});

describe("shapeSize", () => {
  it("finds a file of small squares at each parcel's point scattered", () => {
    // Manassas Park's file: a 6-metre square at each parcel, 300 metres apart.
    const specks = fc(
      Array.from({ length: 100 }, (_, i) =>
        square(-77.47 + (i % 10) * 0.003, 38.78 + Math.floor(i / 10) * 0.003, 0.00007),
      ),
    );
    const s = shapeSize(specks);
    expect(s?.scattered).toBe(true);
    expect(s?.metres).toBeGreaterThan(5);
    expect(s?.metres).toBeLessThan(8);
  });

  it("leaves parcels side by side as shapes", () => {
    const lots = fc(
      Array.from({ length: 100 }, (_, i) =>
        square(-77.47 + (i % 10) * 0.0003, 38.78 + Math.floor(i / 10) * 0.0003, 0.00028),
      ),
    );
    expect(shapeSize(lots)?.scattered).toBe(false);
  });

  it("has nothing to say without polygons", () => {
    expect(shapeSize(fc([]))).toBeNull();
  });
});
