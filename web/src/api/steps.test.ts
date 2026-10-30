import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { after, stepChanged } from "./steps";

describe("the steps after a step", () => {
  it("follows the pipeline down, however far", () => {
    expect(after("bring-in")).toEqual(["assemble", "clean", "prepare", "vartest", "model", "ratio"]);
    expect(after("clean").sort()).toEqual(["model", "prepare", "ratio", "vartest"]);
    expect(after("model")).toEqual([]);
  });
});

describe("a step changed", () => {
  it("asks again for it, what its screen also shows, and every step after it, for this project only", () => {
    const qc = new QueryClient();
    const keys = [
      ["clean", "p1"],
      ["clean-time", "p1"],
      ["prepare", "p1"],
      ["ratio", "p1"],
      ["model", "p1"],
      ["assemble", "p1"],
      ["prepare", "p2"],
    ];
    for (const k of keys) qc.setQueryData(k, { status: "done" });
    stepChanged(qc, "p1", "clean");
    const stale = (k: string[]) => qc.getQueryState(k)?.isInvalidated;
    expect(stale(["clean", "p1"])).toBe(true);
    expect(stale(["clean-time", "p1"])).toBe(true);
    expect(stale(["prepare", "p1"])).toBe(true);
    expect(stale(["ratio", "p1"])).toBe(true);
    expect(stale(["model", "p1"])).toBe(true);
    expect(stale(["assemble", "p1"])).toBe(false); // before it: unchanged
    expect(stale(["prepare", "p2"])).toBe(false); // another project
  });

  it("leaves the step itself alone when the caller already has its new state", () => {
    const qc = new QueryClient();
    qc.setQueryData(["clean", "p1"], { status: "done" });
    qc.setQueryData(["prepare", "p1"], { status: "done" });
    stepChanged(qc, "p1", "clean", false);
    expect(qc.getQueryState(["clean", "p1"])?.isInvalidated).toBe(false);
    expect(qc.getQueryState(["prepare", "p1"])?.isInvalidated).toBe(true);
  });

  it("a model setup change also asks the variable tests again (what was tested is judged against it)", () => {
    const qc = new QueryClient();
    qc.setQueryData(["vartest", "p1"], { status: "done" });
    stepChanged(qc, "p1", "model");
    expect(qc.getQueryState(["vartest", "p1"])?.isInvalidated).toBe(true);
  });
});
