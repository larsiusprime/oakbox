import { describe, expect, it } from "vitest";
import type { ModelGroup } from "../api/client";
import { newGroup } from "./groups";

const COLORS = ["#a00", "#0a0", "#00a"];

describe("newGroup", () => {
  it("takes its id from its name, and the first colour not used", () => {
    const x = newGroup("Single family", [], COLORS);
    expect(x).toMatchObject({ id: "single_family", name: "Single family", color: "#a00", modeled: null });
    expect(x.rule).toEqual({ join: "any", conditions: [] });
  });

  it("numbers an id that's taken, and skips colours in use", () => {
    const one = newGroup("Condo", [], COLORS);
    const two = newGroup("Condo", [one], COLORS);
    expect(two.id).toBe("condo_2");
    expect(two.color).toBe("#0a0");
    expect(newGroup("Condo", [one, two], COLORS).id).toBe("condo_3");
  });

  it("names a group of no letters 'group', and cycles colours once all are used", () => {
    const all: ModelGroup[] = COLORS.map((c, i) => ({ ...newGroup(`g${i}`, [], COLORS), color: c }));
    const x = newGroup("!!!", all, COLORS);
    expect(x.id).toBe("group");
    expect(x.color).toBe("#a00");
  });
});
