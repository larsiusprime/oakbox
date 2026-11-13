import { describe, expect, it } from "vitest";
import { changeCells, type Sale } from "./TimeMap";

const DAY = 86_400_000;
const t0 = Date.UTC(2021, 0, 1);
const t1 = Date.UTC(2024, 0, 1);

/** n sales a year (first and last) at one place, priced `then` and `now`. */
function at(tag: string, lon: number, lat: number, n: number, then: number, now: number, spread = 0): Sale[] {
  const out: Sale[] = [];
  for (let k = 0; k < n; k++) {
    // Spread: across that many degrees, so no quarter of its square keeps them all.
    const dx = spread * ((k % 3) / 2 - 0.5);
    const dy = spread * ((Math.floor(k / 3) % 3) / 2 - 0.5);
    out.push({ key: `${tag}a${k}`, t: t0 + k * DAY, per: then, lon: lon + dx, lat: lat + dy });
    out.push({ key: `${tag}b${k}`, t: t1 - k * DAY, per: now, lon: lon + dx, lat: lat + dy });
  }
  return out;
}

const index = [
  { day: "2021-06-01", value: 1 },
  { day: "2023-06-01", value: 1.5 },
];

describe("changeCells", () => {
  it("says how far each square moved, first year to last, against the index", () => {
    // Two places 30 km apart: different big squares.
    const r = changeCells(
      [...at("a", -79.8, 36.0, 10, 100, 200), ...at("c", -79.45, 36.2, 10, 100, 100)],
      index,
      t0,
      t1,
      125,
    );
    expect(r?.index).toBeCloseTo(0.5);
    const moves = (r?.cells ?? []).map((c) => Math.round(c.change * 100)).sort((a, b) => a - b);
    expect(moves).toEqual([0, 100]);
    // Doubled where the index says +50%: a third faster; flat: a third slower.
    const diffs = (r?.cells ?? []).map((c) => Math.round(c.diff * 1000) / 1000).sort((a, b) => a - b);
    expect(diffs).toEqual([-0.333, 0.333]);
  });
  it("splits dense places into small squares and keeps sparse ones large", () => {
    // Two dense spots 3 km apart in one big square: they split apart. A thin spot alone keeps a big square.
    const dense = [...at("a", -79.8, 36.0, 40, 100, 150), ...at("b", -79.767, 36.0, 40, 100, 150)];
    const r = changeCells([...dense, ...at("c", -79.3, 36.3, 9, 100, 150, 0.06)], index, t0, t1, 125);
    const sides = (r?.cells ?? []).map((c) =>
      Math.round(((c.polygon[1]?.[0] ?? 0) - (c.polygon[0]?.[0] ?? 0)) * 1e4),
    );
    expect(sides.length).toBe(3);
    const big = Math.max(...sides);
    expect(sides.filter((s) => s < big).length).toBe(2);
  });
  it("never goes finer than the zoom allows", () => {
    const r = changeCells(at("a", -79.8, 36.0, 400, 100, 150), index, t0, t1, 4000);
    const side = (r?.cells[0]?.polygon[1]?.[0] ?? 0) - (r?.cells[0]?.polygon[0]?.[0] ?? 0);
    expect(r?.cells).toHaveLength(1);
    expect(side * 111_320 * Math.cos((36 * Math.PI) / 180)).toBeCloseTo(4000, -1);
  });
  it("leaves out squares with too few sales in either year, and windows shorter than a year and a half", () => {
    expect(changeCells(at("a", -79.8, 36.0, 7, 100, 150), index, t0, t1, 125)?.cells).toHaveLength(0);
    expect(changeCells(at("a", -79.8, 36.0, 20, 100, 150), [], t0, t0 + 300 * DAY, 125)).toBeNull();
  });
});
