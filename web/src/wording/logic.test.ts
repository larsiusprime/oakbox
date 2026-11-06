import { describe, expect, it } from "vitest";
import { t } from ".";
import { say } from "./logic";

describe("the notice above the tabs", () => {
  it("names the tabs without their numbers", () => {
    expect(say.tabs.waits(t.tabs.values, t.tabs.sales)).toBe("Models waits for Sales.");
    expect(say.tabs.runAgain(t.tabs.bring)).toBe(
      "Inputs is out of date: run it again, then press Looks right.",
    );
    expect(say.tabs.pressLooksRight("3. Sales")).toBe("Press Looks right on Sales first.");
  });
});
