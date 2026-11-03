import { describe, expect, it } from "vitest";
import { matches } from "./Combo";

describe("typing in a dropdown", () => {
  it("keeps the names holding what's typed, anywhere, case aside", () => {
    const names = ["YEAR_BUILT", "EFF_YEAR", "HEATED_AREA", "US Dollar ($)"];
    expect(names.filter((n) => matches(n, "year"))).toEqual(["YEAR_BUILT", "EFF_YEAR"]);
    expect(names.filter((n) => matches(n, " DOL "))).toEqual(["US Dollar ($)"]);
    expect(names.filter((n) => matches(n, ""))).toEqual(names);
  });
});
