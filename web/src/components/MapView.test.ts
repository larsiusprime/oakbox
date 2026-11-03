import { describe, expect, it } from "vitest";
import { boundsOf, boundsOfGeoJson, rgba } from "./MapView";

describe("the map's helpers", () => {
  it("reads colours as deck.gl takes them", () => {
    expect(rgba("#1d5bb8")).toEqual([29, 91, 184, 255]);
    expect(rgba("#fff", 0.5)).toEqual([255, 255, 255, 128]);
    expect(rgba("rgb(10, 20, 30)", 0)).toEqual([10, 20, 30, 0]);
  });

  it("boxes points and shapes, leaving out what has no place", () => {
    expect(boundsOf([])).toBeNull();
    expect(
      boundsOf(
        [
          [-80, 36],
          [-79, 35],
          [Number.NaN, 40],
        ],
        [
          null,
          [
            [-81, 36.5],
            [-80.5, 37],
          ],
        ],
      ),
    ).toEqual([
      [-81, 35],
      [-79, 37],
    ]);
    const fc: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [1, 2],
                [3, 4],
                [1, 4],
                [1, 2],
              ],
            ],
          },
        },
      ],
    };
    expect(boundsOfGeoJson(fc)).toEqual([
      [1, 2],
      [3, 4],
    ]);
  });
});
