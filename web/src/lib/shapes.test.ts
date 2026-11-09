import { describe, expect, it } from "vitest";
import { readShapes, type Shapes, shapeSize, shapesBounds, toBinary, triangulate } from "./shapes";

/** shapes.bin as the app writes it (groups._binary), from each parcel's polygons: rings of [lon, lat]. */
type Polygon = number[][][]; // rings of [lon, lat]

function file(parcels: Polygon[][]): ArrayBuffer {
  const pp = [0];
  const pr = [0];
  const rc = [0];
  const xy: number[] = [];
  for (const polys of parcels) {
    for (const rings of polys) {
      for (const ring of rings) {
        for (const [x = 0, y = 0] of ring) xy.push(Math.round(x * 1e6), Math.round(y * 1e6));
        rc.push(xy.length / 2);
      }
      pr.push(rc.length - 1);
    }
    pp.push(pr.length - 1);
  }
  const ints = [parcels.length, pr.length - 1, rc.length - 1, xy.length / 2, ...pp, ...pr, ...rc, ...xy];
  const buf = new ArrayBuffer(8 + ints.length * 4);
  new Uint8Array(buf).set(new TextEncoder().encode("OAKSHP01"));
  new Int32Array(buf, 8).set(ints);
  return buf;
}

// A square side `d` degrees wide with its corner at (x, y), as one polygon of one ring.
const square = (x: number, y: number, d: number): Polygon => [
  [
    [x, y],
    [x + d, y],
    [x + d, y + d],
    [x, y + d],
    [x, y],
  ],
];

describe("the map's shapes", () => {
  const holed: Polygon = [
    [
      [0, 0],
      [4, 0],
      [4, 4],
      [0, 4],
      [0, 0],
    ],
    [
      [1, 1],
      [2, 1],
      [2, 2],
      [1, 1],
    ],
  ];
  const s: Shapes = readShapes(
    // a square; no shape; a holed polygon and a square (a multipolygon)
    file([[square(-77.47, 38.78, 0.001)], [], [holed, square(10, 10, 1)]]),
  );

  it("reads the file the app writes", () => {
    expect(s.parcels).toBe(3);
    expect([...s.parcelPolygons]).toEqual([0, 1, 1, 3]);
    expect(s.xy[0]).toBeCloseTo(-77.47, 6);
    expect(shapesBounds(s)).toEqual([
      [-77.47, 0],
      [11, 38.781],
    ]);
  });

  it("makes deck.gl's binary features, each corner its parcel's", () => {
    const b = toBinary(s).polygons;
    expect([...b.polygonIndices.value]).toEqual([0, 5, 14, 19]);
    expect([...b.primitivePolygonIndices.value]).toEqual([0, 5, 10, 14, 19]); // the hole: a ring of its polygon
    expect(b.globalFeatureIds.value[0]).toBe(0);
    expect(b.globalFeatureIds.value[5]).toBe(2);
    expect(b.numericProps.parcel.value[18]).toBe(2);
    // A few parcels: only theirs, still by their own index.
    const one = toBinary(s, [2]).polygons;
    expect(one.positions.value.length).toBe(14 * 2);
    expect([...new Set(one.featureIds.value)]).toEqual([2]);
    expect(toBinary(s, [1]).polygons.polygonIndices.value.length).toBe(1); // no shape: nothing
  });

  it("finds a file of small squares at each parcel's point scattered", () => {
    // Manassas Park's file: a 6-metre square at each parcel, 300 metres apart.
    const specks = readShapes(
      file(
        Array.from({ length: 100 }, (_, i) => [
          square(-77.47 + (i % 10) * 0.003, 38.78 + Math.floor(i / 10) * 0.003, 0.00007),
        ]),
      ),
    );
    const z = shapeSize(specks);
    expect(z?.scattered).toBe(true);
    expect(z?.metres).toBeGreaterThan(5);
    expect(z?.metres).toBeLessThan(8);
  });

  it("leaves parcels side by side as shapes", () => {
    const lots = readShapes(
      file(
        Array.from({ length: 100 }, (_, i) => [
          square(-77.47 + (i % 10) * 0.0003, 38.78 + Math.floor(i / 10) * 0.0003, 0.00028),
        ]),
      ),
    );
    expect(shapeSize(lots)?.scattered).toBe(false);
    expect(shapeSize(readShapes(file([[]])))).toBeNull();
  });
});

describe("triangulate", () => {
  it("leaves a polygon's holes unfilled", () => {
    // A 4×4 square with a 2×2 hole in its middle (rings closed, as shapes.bin keeps them).
    const outer = [0, 0, 4, 0, 4, 4, 0, 4, 0, 0];
    const hole = [1, 1, 1, 3, 3, 3, 3, 1, 1, 1];
    const positions = Float64Array.from([...outer, ...hole]);
    const tri = triangulate(positions, Uint32Array.from([0, 10]), Uint32Array.from([0, 5, 10]));
    expect(tri.length % 3).toBe(0);
    let area = 0;
    for (let k = 0; k < tri.length; k += 3) {
      const [a, b, c] = [tri[k] ?? 0, tri[k + 1] ?? 0, tri[k + 2] ?? 0].map((i) => [
        positions[2 * i] ?? 0,
        positions[2 * i + 1] ?? 0,
      ]);
      area +=
        Math.abs(
          ((b?.[0] ?? 0) - (a?.[0] ?? 0)) * ((c?.[1] ?? 0) - (a?.[1] ?? 0)) -
            ((c?.[0] ?? 0) - (a?.[0] ?? 0)) * ((b?.[1] ?? 0) - (a?.[1] ?? 0)),
        ) / 2;
      // No triangle's middle is in the hole.
      const mx = ((a?.[0] ?? 0) + (b?.[0] ?? 0) + (c?.[0] ?? 0)) / 3;
      const my = ((a?.[1] ?? 0) + (b?.[1] ?? 0) + (c?.[1] ?? 0)) / 3;
      expect(mx > 1 && mx < 3 && my > 1 && my < 3).toBe(false);
    }
    expect(area).toBeCloseTo(16 - 4);
  });
});
