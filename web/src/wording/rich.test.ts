import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { escapeArgs, isRich, plainText, rich } from "./rich";

const html = (s: string) => renderToStaticMarkup(rich(s) as never);

describe("formatting in the wording", () => {
  it("makes **bold** and *italic*", () => {
    expect(html("a **sales record** and a *parcel universe*")).toBe(
      "a <strong>sales record</strong> and a <em>parcel universe</em>",
    );
    expect(html("**bold *and italic* inside**")).toBe("<strong>bold <em>and italic</em> inside</strong>");
  });
  it("keeps \\* an asterisk, and an unclosed one as written", () => {
    expect(html("2 \\* 3 is **six**")).toBe("2 * 3 is <strong>six</strong>");
    expect(html("a **dangling one")).toBe("a **dangling one");
  });
  it("knows which messages are formatted", () => {
    expect(isRich("a **b**")).toBe(true);
    expect(isRich("*x*")).toBe(true);
    expect(isRich("^\\s\\*(?P<s>x)")).toBe(false);
    expect(isRich("plain")).toBe(false);
    expect(plainText("^\\s\\*x")).toBe("^\\s*x");
  });
  it("treats an argument's asterisks as text", () => {
    const args = escapeArgs({ file: "a*b*.csv", n: 3 });
    expect(html(`Open **${args.file}**`)).toBe("Open <strong>a*b*.csv</strong>");
    expect(args.n).toBe(3);
  });
});
