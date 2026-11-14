// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { covered, shortPath, whatWas } from "./perf";

describe("perf", () => {
  it("counts overlapping time once, and only inside the window", () => {
    expect(
      covered(
        [
          [0, 10],
          [5, 20],
          [30, 40],
        ],
        2,
        35,
      ),
    ).toBe(23);
    expect(covered([], 0, 10)).toBe(0);
  });

  it("shortens a project's paths and leaves off the query", () => {
    expect(shortPath("http://127.0.0.1:8000/api/projects/abc123/wizard/fields/sale_date?x=secret")).toBe(
      "/api/projects/…/wizard/fields/sale_date",
    );
  });

  it("names what was clicked by its label or text", () => {
    document.body.innerHTML = `<div role="option"><span id="in">Date</span></div><div role="option"><b id="two">Amount</b>\n<i>1, 2, 3</i></div><button aria-label="Close"><svg id="x"></svg></button>`;
    expect(whatWas(document.getElementById("in"))).toBe("Date");
    expect(whatWas(document.getElementById("x"))).toBe("Close");
    expect(whatWas(document.getElementById("two"))).toBe("Amount");
  });
});
