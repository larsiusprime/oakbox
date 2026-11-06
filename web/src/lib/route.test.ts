import { describe, expect, it } from "vitest";
import { hashOf, parseHash, type Route } from "./route";

describe("the address", () => {
  it("reads every place it writes", () => {
    const places: Route[] = [
      { name: "home" },
      { name: "new" },
      { name: "project", id: "a1b2c3", tab: null, step: null },
      { name: "project", id: "a1b2c3", tab: "sales", step: null },
      { name: "project", id: "a1b2c3", tab: "fields", step: "big_five" },
    ];
    for (const r of places) expect(parseHash(hashOf(r))).toEqual(r);
  });

  it("keeps a step in the address for the Data tab only", () => {
    expect(hashOf({ name: "project", id: "p", tab: "values", step: "finalize" })).toBe("#/projects/p/values");
    expect(parseHash("#/projects/p/values/finalize")).toEqual({
      name: "project",
      id: "p",
      tab: "values",
      step: null,
    });
  });

  it("reads anything else as home", () => {
    expect(parseHash("")).toEqual({ name: "home" });
    expect(parseHash("#/projects/P!")).toEqual({ name: "home" });
    expect(parseHash("#/projects/p/nonsense")).toEqual({ name: "project", id: "p", tab: null, step: null });
  });
});
