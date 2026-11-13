import { describe, expect, it } from "vitest";
import { changeCells, type Sale } from "./TimeMap";

const DAY = 86_400_000;
const t0 = Date.UTC(2021, 0, 1);
const t1 = Date.UTC(2024, 0, 1);

/** Sales in two places: a first year and a last year each, priced so one place doubled and the other stayed. */
function sales(): Sale[] {
  const out: Sale[] = [];
  for (let k = 0; k < 10; k++) {
    const early = t0 + k * 20 * DAY;
    const late = t1 - k * 20 * DAY;
    out.push({ key: `a${k}`, t: early, per: 100, lon: -79.8, lat: 36.0 });
    out.push({ key: `b${k}`, t: late, per: 200, lon: -79.8, lat: 36.0 });
    out.push({ key: `c${k}`, t: early, per: 100, lon: -79.5, lat: 36.2 });
    out.push({ key: `d${k}`, t: late, per: 100, lon: -79.5, lat: 36.2 });
  }
  return out;
}

describe("changeCells", () => {
  it("says how far each square moved, first year to last, against the index", () => {
    const index = [
      { day: "2021-06-01", value: 1 },
      { day: "2023-06-01", value: 1.5 },
    ];
    const r = changeCells(sales(), index, t0, t1);
    expect(r).not.toBeNull();
    expect(r?.index).toBeCloseTo(0.5);
    const moves = (r?.cells ?? []).map((c) => Math.round(c.change * 100)).sort((a, b) => a - b);
    expect(moves).toEqual([0, 100]);
    // Doubled where the index says +50%: a third faster; flat: a third slower.
    const diffs = (r?.cells ?? []).map((c) => Math.round(c.diff * 1000) / 1000).sort((a, b) => a - b);
    expect(diffs).toEqual([-0.333, 0.333]);
  });
  it("leaves out squares with too few sales in either year, and windows shorter than a year and a half", () => {
    const few = sales().filter((s) => !s.key.startsWith("d") || Number(s.key.slice(1)) < 3);
    expect(changeCells(few, [], t0, t1)?.cells).toHaveLength(1);
    expect(changeCells(sales(), [], t0, t0 + 300 * DAY)).toBeNull();
  });
});
