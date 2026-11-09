import { describe, expect, it } from "vitest";
import { shareOf, valueAt } from "./FieldHistogram";

describe("the range track, by percentile", () => {
  // Five points (every 25%): one huge value at the end, as a county's biggest farm.
  const qs = [1, 2, 3, 4, 1_000_000];
  it("puts the median at the middle, whatever the outliers", () => {
    expect(shareOf(qs, 3)).toBe(0.5);
    expect(valueAt(qs, 0.5)).toBe(3);
    expect(shareOf(qs, 4)).toBe(0.75);
  });
  it("runs from the smallest to the largest", () => {
    expect(shareOf(qs, 0)).toBe(0);
    expect(shareOf(qs, 2_000_000)).toBe(1);
    expect(valueAt(qs, 0)).toBe(1);
    expect(valueAt(qs, 1)).toBe(1_000_000);
  });
  it("goes between two points in proportion", () => {
    expect(shareOf(qs, 2.5)).toBeCloseTo(0.375);
    expect(valueAt(qs, 0.375)).toBeCloseTo(2.5);
  });
  it("puts a run of equal values at its middle", () => {
    expect(shareOf([0, 5, 5, 5, 10], 5)).toBe(0.5);
  });
});
