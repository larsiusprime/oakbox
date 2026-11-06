import { describe, expect, it } from "vitest";
import { type Gates, lockedTabs } from "./tabs";

const all: Gates = {
  accepted: true,
  grouped: true,
  checked: true,
  hasValues: true,
  prepared: true,
  finalized: true,
};
const locked = (g: Partial<Gates>) => [...lockedTabs({ ...all, ...g })].sort();

describe("the tabs that wait", () => {
  it("none, once every step before them is accepted", () => {
    expect(locked({})).toEqual([]);
  });

  it("each step locks the tabs that start from it", () => {
    expect(locked({ accepted: false })).toEqual(["groups"]);
    expect(locked({ grouped: false })).toEqual(["sales"]);
    expect(locked({ checked: false })).toEqual(["check", "values", "variables"]);
    expect(locked({ prepared: false })).toEqual(["values"]);
    expect(locked({ finalized: false })).toEqual(["report"]);
  });

  it("Evaluate waits for existing values to check, too", () => {
    expect(locked({ hasValues: false })).toEqual(["check"]);
  });

  it("Data, Metadata and Inputs never wait", () => {
    const none = lockedTabs({
      accepted: false,
      grouped: false,
      checked: false,
      hasValues: false,
      prepared: false,
      finalized: false,
    });
    for (const open of ["metadata", "fields", "bring"] as const) expect(none.has(open)).toBe(false);
  });
});
