// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { t } from "../wording";
import { MultiPick } from "./MultiPick";

afterEach(cleanup);

const values = ["Condos", "Apartments", "Single-family", "Agricultural"].map((v) => ({ value: v }));

describe("MultiPick", () => {
  it("saves nothing while open, and the final choice once when it closes", () => {
    const change = vi.fn();
    render(<MultiPick label="Model groups" values={values} chosen={["Condos"]} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: /Model groups/ }));
    // Ticks, Clear and a tick again: each shows at once, none saves.
    fireEvent.click(screen.getByRole("checkbox", { name: /Apartments/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Single-family/ }));
    expect((screen.getByRole("checkbox", { name: /Single-family/ }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(t.multiPick.clear) }));
    expect((screen.getByRole("checkbox", { name: /Condos/ }) as HTMLInputElement).checked).toBe(false);
    fireEvent.click(screen.getByRole("checkbox", { name: /Agricultural/ }));
    expect(change).not.toHaveBeenCalled();
    // Closed (Escape): one save, of what was chosen last.
    act(() => {
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    });
    expect(change).toHaveBeenCalledOnce();
    expect(change).toHaveBeenCalledWith(["Agricultural"]);
  });

  it("saves nothing when closed unchanged", () => {
    const change = vi.fn();
    render(<MultiPick label="Model groups" values={values} chosen={["Condos"]} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: /Model groups/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Apartments/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Apartments/ }));
    act(() => {
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    });
    expect(change).not.toHaveBeenCalled();
  });
});
