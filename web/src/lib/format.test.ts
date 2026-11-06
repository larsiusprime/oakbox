import { describe, expect, it } from "vitest";
import { amount, band, clock, day, money, moneyShort, num, pct, short, signed, size, when } from "./format";

// The checks run with the computer's locale; these are written for English (CI's), where it shows.
describe("how numbers are written", () => {
  it("fixes decimals, and says — for none", () => {
    expect(num(1234.5, 1)).toBe("1,234.5");
    expect(num(2)).toBe("2");
    expect(num(null)).toBe("—");
    expect(num(undefined, 3)).toBe("—");
  });

  it("signs with a true minus", () => {
    expect(signed(0.152, 3)).toBe("+0.152");
    expect(signed(-12.6, 1)).toBe("−12.6");
    expect(signed(0, 1)).toBe("+0.0");
  });

  it("writes a share whole, but within a point of 0 or 100", () => {
    expect(pct(0.37)).toBe("37%");
    expect(pct(0.004)).toBe("0.4%");
    expect(pct(0.996)).toBe("99.6%");
    expect(pct(0)).toBe("0%");
    expect(pct(1)).toBe("100%");
  });
});

describe("how money is written", () => {
  it("in whole units, cents under 100, two figures under 1", () => {
    expect(money(246000, "USD")).toBe("$246,000");
    expect(money(12.5, "USD")).toBe("$12.50");
    expect(money(0.0123, "USD")).toBe("$0.012");
    expect(money(null, "USD")).toBe("—");
  });

  it("short", () => {
    expect(moneyShort(246000, "USD")).toBe("$246K");
    expect(moneyShort(1_250_000, "USD")).toBe("$1.25M");
    expect(amount("$", 246000)).toBe("$246K");
    expect(amount("$", 1_250_000)).toBe("$1.25M");
    expect(amount("$", 10)).toBe("$10");
    expect(amount("$", 2.5)).toBe("$2.5");
  });
});

describe("dates, times and sizes", () => {
  it("a day, a clock, a file's size", () => {
    expect(day("2025-11-01T14:05:00")).toBe("2025-11-01");
    expect(day(null)).toBe("—");
    expect(clock(187)).toBe("3:07");
    expect(clock(-4)).toBe("0:00");
    expect(size(640 * 1024)).toBe("640 KB");
    expect(size(12 * 2 ** 20)).toBe("12 MB");
    expect(size(1.4 * 2 ** 30)).toBe("1.4 GB");
    expect(size(10)).toBe("1 KB");
  });

  it("says today for today", () => {
    expect(when(new Date().toISOString())).toMatch(/^today at /);
    expect(when("2020-01-02T03:04:00")).toMatch(/ at /);
  });
});

describe("rows and long values", () => {
  it("shades a repeated ID's rows alike, and otherwise every other row", () => {
    expect([0, 1, 2].map((i) => band(null, i))).toEqual(["band-a", "band-b", "band-a"]);
    expect([0, 1, 2].map((i) => band([0, 0, 1], i))).toEqual(["band-a", "band-a", "band-b"]);
  });

  it("cuts a value short with an ellipsis", () => {
    const cut = short("#".repeat(255));
    expect(cut).toHaveLength(40);
    expect(cut.endsWith("…")).toBe(true);
    expect(short("parcels.csv")).toBe("parcels.csv");
  });
});
