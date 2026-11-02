import { beforeAll, describe, expect, it } from "vitest";
import { currentFrame, lastStep, lastTab, publishFrame, remember, rememberTab, setWhere } from "./place";

beforeAll(() => {
  // The test runner has no browser storage: a stand-in.
  const kept = new Map<string, string>();
  Object.assign(globalThis, {
    localStorage: {
      getItem: (k: string) => kept.get(k) ?? null,
      setItem: (k: string, v: string) => kept.set(k, v),
    },
  });
});

describe("where you last were", () => {
  it("remembers each project's tab and each tab's step", () => {
    remember("p1", "values", "final", "Finalize");
    remember("p1", "sales", "aside", "Sales set aside");
    expect(lastTab("p1")).toBe("sales");
    expect(lastStep("p1", "values")).toEqual({ key: "final", title: "Finalize" });
    rememberTab("p1", "values");
    expect(lastTab("p1")).toBe("values");
    expect(lastTab("never")).toBeNull();
  });

  it("a step list going away clears only its own steps from the plate", () => {
    setWhere({ projectId: "p2", tab: "values" });
    const old = {};
    const next = {};
    const go = () => {};
    publishFrame({ steps: [{ key: "how", title: "How they did", status: "done" }], current: "how", go }, old);
    publishFrame(
      { steps: [{ key: "final", title: "Finalize", status: "done" }], current: "final", go },
      next,
    );
    // The old tab's list leaves after the new one has arrived: the new one stays.
    publishFrame(null, old);
    expect(currentFrame()?.current).toBe("final");
    publishFrame(null, next);
    expect(currentFrame()).toBeNull();
    expect(lastStep("p2", "values")?.key).toBe("final");
  });
});
