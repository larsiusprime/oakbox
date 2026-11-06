/**
 * The parcel shapes for the map, as the app sends them (shapes.bin, groups._binary): a few arrays, not GeoJSON text.
 * Made into deck.gl's binary features (the layout loaders.gl's geojsonToBinary makes) for GeoJsonLayer, whole or for
 * a few parcels, with each corner carrying its parcel's index: what's clicked and coloured.
 */

export type Shapes = {
  parcels: number;
  /** Each parcel's polygons start here (parcels + 1). */
  parcelPolygons: Int32Array;
  /** Each polygon's rings start here: its outline, then its holes (polygons + 1). */
  polygonRings: Int32Array;
  /** Each ring's corners start here (rings + 1). */
  ringCorners: Int32Array;
  /** Longitude, latitude of each corner, in degrees. */
  xy: Float64Array;
};

const MAGIC = "OAKSHP01";

export function readShapes(buf: ArrayBuffer): Shapes {
  const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 8));
  if (magic !== MAGIC) throw new Error("Not a shapes file.");
  const head = new Int32Array(buf, 8, 4);
  const [parcels = 0, polygons = 0, rings = 0, corners = 0] = head;
  let at = 24;
  const take = (n: number) => {
    const a = new Int32Array(buf, at, n);
    at += n * 4;
    return a;
  };
  const parcelPolygons = take(parcels + 1);
  const polygonRings = take(polygons + 1);
  const ringCorners = take(rings + 1);
  const raw = take(corners * 2);
  const xy = new Float64Array(raw.length);
  for (let i = 0; i < raw.length; i++) xy[i] = (raw[i] ?? 0) / 1e6;
  return { parcels, parcelPolygons, polygonRings, ringCorners, xy };
}

/** deck.gl's binary features (loaders.gl's BinaryFeatureCollection), as far as GeoJsonLayer reads it. */
export type BinaryShapes = {
  shape: "binary-feature-collection";
  points: ReturnType<typeof noPoints>;
  lines: ReturnType<typeof noLines>;
  polygons: {
    type: "Polygon";
    positions: { value: Float64Array; size: 2 };
    polygonIndices: { value: Uint32Array; size: 1 };
    primitivePolygonIndices: { value: Uint32Array; size: 1 };
    featureIds: { value: Uint32Array; size: 1 };
    globalFeatureIds: { value: Uint32Array; size: 1 };
    numericProps: { parcel: { value: Float32Array; size: 1 } };
    properties: object[];
  };
};

const noPoints = () => ({
  type: "Point" as const,
  positions: { value: new Float64Array(0), size: 2 },
  featureIds: { value: new Uint32Array(0), size: 1 },
  globalFeatureIds: { value: new Uint32Array(0), size: 1 },
  numericProps: {},
  properties: [] as object[],
});
const noLines = () => ({
  type: "LineString" as const,
  positions: { value: new Float64Array(0), size: 2 },
  pathIndices: { value: new Uint32Array([0]), size: 1 },
  featureIds: { value: new Uint32Array(0), size: 1 },
  globalFeatureIds: { value: new Uint32Array(0), size: 1 },
  numericProps: {},
  properties: [] as object[],
});

/** The binary features of these parcels (every parcel when not given). A feature's `properties.parcel` and a
 * pick's `index` are its parcel's index. */
export function toBinary(s: Shapes, which?: Iterable<number>): BinaryShapes {
  const ids = which ? [...which] : null;
  const count = ids ? ids.length : s.parcels;
  const parcelAt = (k: number) => (ids ? (ids[k] ?? -1) : k);
  // Sizes first, then fill.
  let nPoly = 0;
  let nRing = 0;
  let nCorner = 0;
  for (let k = 0; k < count; k++) {
    const p = parcelAt(k);
    if (p < 0 || p >= s.parcels) continue;
    const a = s.parcelPolygons[p] ?? 0;
    const b = s.parcelPolygons[p + 1] ?? 0;
    nPoly += b - a;
    const r0 = s.polygonRings[a] ?? 0;
    const r1 = s.polygonRings[b] ?? 0;
    nRing += r1 - r0;
    nCorner += (s.ringCorners[r1] ?? 0) - (s.ringCorners[r0] ?? 0);
  }
  const positions = new Float64Array(nCorner * 2);
  const polygonIndices = new Uint32Array(nPoly + 1);
  const primitive = new Uint32Array(nRing + 1);
  const ofParcel = new Uint32Array(nCorner);
  const parcelProp = new Float32Array(nCorner);
  let pi = 0;
  let ri = 0;
  let ci = 0;
  for (let k = 0; k < count; k++) {
    const p = parcelAt(k);
    if (p < 0 || p >= s.parcels) continue;
    for (let poly = s.parcelPolygons[p] ?? 0; poly < (s.parcelPolygons[p + 1] ?? 0); poly++) {
      polygonIndices[pi++] = ci;
      for (let ring = s.polygonRings[poly] ?? 0; ring < (s.polygonRings[poly + 1] ?? 0); ring++) {
        primitive[ri++] = ci;
        const c0 = s.ringCorners[ring] ?? 0;
        const c1 = s.ringCorners[ring + 1] ?? 0;
        positions.set(s.xy.subarray(c0 * 2, c1 * 2), ci * 2);
        ofParcel.fill(p, ci, ci + c1 - c0);
        parcelProp.fill(p, ci, ci + c1 - c0);
        ci += c1 - c0;
      }
    }
  }
  polygonIndices[pi] = ci;
  primitive[ri] = ci;
  return {
    shape: "binary-feature-collection",
    points: noPoints(),
    lines: noLines(),
    polygons: {
      type: "Polygon",
      positions: { value: positions, size: 2 },
      polygonIndices: { value: polygonIndices, size: 1 },
      primitivePolygonIndices: { value: primitive, size: 1 },
      featureIds: { value: ofParcel, size: 1 },
      globalFeatureIds: { value: ofParcel, size: 1 },
      numericProps: { parcel: { value: parcelProp, size: 1 } },
      properties: [],
    },
  };
}

/** The box around every corner: [[west, south], [east, north]], or undefined with none. */
export function shapesBounds(s: Shapes): [[number, number], [number, number]] | undefined {
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
  for (let i = 0; i + 1 < s.xy.length; i += 2) {
    const x = s.xy[i] ?? 0;
    const y = s.xy[i + 1] ?? 0;
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  return Number.isFinite(x0)
    ? [
        [x0, y0],
        [x1, y1],
      ]
    : undefined;
}

// Shapes covering under this share of the ground they're spread over are scattered specks: some parcel files hold
// only a small square at each parcel's point.
const SCATTERED = 0.1;

/** The shapes' typical size (the median of each parcel's longer side, in metres), and whether they're scattered
 * specks. Null with no shapes. */
export function shapeSize(s: Shapes): { metres: number; scattered: boolean } | null {
  const sides: number[] = [];
  let cover = 0;
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
  const step = Math.max(1, Math.floor(s.parcels / 4000));
  for (let p = 0; p < s.parcels; p += step) {
    const r0 = s.polygonRings[s.parcelPolygons[p] ?? 0] ?? 0;
    const r1 = s.polygonRings[s.parcelPolygons[p + 1] ?? 0] ?? 0;
    const c0 = s.ringCorners[r0] ?? 0;
    const c1 = s.ringCorners[r1] ?? 0;
    if (c1 <= c0) continue;
    let [a, b, c, d] = [Infinity, Infinity, -Infinity, -Infinity];
    for (let i = c0; i < c1; i++) {
      const x = s.xy[i * 2] ?? 0;
      const y = s.xy[i * 2 + 1] ?? 0;
      a = Math.min(a, x);
      b = Math.min(b, y);
      c = Math.max(c, x);
      d = Math.max(d, y);
    }
    const k = 111_320 * Math.cos((((b + d) / 2) * Math.PI) / 180);
    const w = (c - a) * k;
    const h = (d - b) * 110_540;
    sides.push(Math.max(w, h));
    cover += w * h;
    [x0, y0, x1, y1] = [Math.min(x0, a), Math.min(y0, b), Math.max(x1, c), Math.max(y1, d)];
  }
  if (!sides.length) return null;
  sides.sort((p, q) => p - q);
  const k = 111_320 * Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
  const ground = (x1 - x0) * k * ((y1 - y0) * 110_540);
  return {
    metres: sides[Math.floor(sides.length / 2)] ?? 0,
    scattered: ground > 0 && cover / ground < SCATTERED,
  };
}
