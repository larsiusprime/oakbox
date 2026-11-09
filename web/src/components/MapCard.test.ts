import { describe, expect, it } from "vitest";
import { tidy } from "./MapCard";

describe("tidy", () => {
  it("rounds a long tail of decimals, keeping the unit", () => {
    expect(tidy("11589.2567924401 sq ft")).toBe("11,589.26 sq ft");
    expect(tidy("0.27 acres")).toBe("0.27 acres");
  });
  it("leaves anything else as written", () => {
    expect(tidy("MULTI-FAMILY<4")).toBe("MULTI-FAMILY<4");
    expect(tidy("2017")).toBe("2017");
    expect(tidy("")).toBe("");
  });
});
