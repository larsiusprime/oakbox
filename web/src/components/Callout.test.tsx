// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { t } from "../wording";
import { Callout, firstSentence } from "./Callout";

afterEach(cleanup);

describe("Callout", () => {
  it("shows its first line folded, and the rest when opened, and folds it away again", () => {
    render(<Callout summary="Some IDs don't match.">Why, and what to do about it.</Callout>);
    const toggle = screen.getByRole("button");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Some IDs don't match.")).toBeTruthy();
    expect(screen.queryByText("Why, and what to do about it.")).toBeNull();
    expect(screen.getByText(t.callout.show)).toBeTruthy();

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Why, and what to do about it.")).toBeTruthy();
    expect(screen.getByText(t.callout.hide)).toBeTruthy();

    fireEvent.click(toggle);
    expect(screen.queryByText("Why, and what to do about it.")).toBeNull();
  });

  it("cuts a text at its first sentence", () => {
    expect(firstSentence("Rows don't match. Here's why: the IDs differ.")).toBe("Rows don't match.");
    expect(firstSentence("No full stop")).toBe("No full stop");
  });
});
