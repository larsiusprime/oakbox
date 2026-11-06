// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { clearUndo, onUndo, type UndoOffer } from "../lib/undo";
import { t } from "../wording";
import { RemoveButton } from "./RemoveButton";

afterEach(() => {
  cleanup();
  clearUndo();
});

describe("RemoveButton", () => {
  it("says what it removes, and removes it", () => {
    const remove = vi.fn();
    render(<RemoveButton what="parks" onPress={remove} />);
    fireEvent.click(screen.getByRole("button", { name: t.buttons.remove({ what: "parks" }) }));
    expect(remove).toHaveBeenCalledOnce();
  });

  it("offers Undo, which puts it back", () => {
    const remove = vi.fn();
    const putBack = vi.fn();
    let offer: UndoOffer | null = null;
    const stop = onUndo((o) => {
      offer = o;
    });
    render(<RemoveButton what="parks" onPress={remove} undo={putBack} />);
    fireEvent.click(screen.getByRole("button"));
    expect(remove).toHaveBeenCalledOnce();
    const made = offer as UndoOffer | null;
    expect(made?.text).toBe(t.buttons.removed({ what: "parks" }));
    made?.restore();
    expect(putBack).toHaveBeenCalledOnce();
    stop();
  });

  it("offers no Undo when it can't be undone", () => {
    let offer: UndoOffer | null = null;
    const stop = onUndo((o) => {
      offer = o;
    });
    render(<RemoveButton what="parks" onPress={() => {}} />);
    fireEvent.click(screen.getByRole("button"));
    expect(offer).toBeNull();
    stop();
  });
});
