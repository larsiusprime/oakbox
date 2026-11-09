// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GroupsPreview, ModelGroup } from "../api/client";
import { t } from "../wording";
import { GroupChecks } from "./GroupChecks";

afterEach(cleanup);

const group = (id: string, name: string): ModelGroup => ({
  id,
  name,
  modeled: null,
  color: "#123456",
  rule: { join: "any", conditions: [] },
  numeric: [],
  keys: [],
});

const stats = (
  id: string,
  modeled: boolean,
  sales: number,
  checks: { level: "ok" | "warn" | "bad"; text: string }[],
) => ({
  id,
  modeled,
  parcels: 1200,
  vacant: 10,
  sales,
  vacant_sales: 2,
  median_price: null,
  first_year: null,
  last_year: null,
  checks,
});

const groups = [group("sf", "Single family"), group("condo", "Condos")];
const preview = {
  assign: [],
  saved: [],
  stats: [
    stats("sf", true, 340, [{ level: "ok", text: "Enough sales" }]),
    stats("condo", false, 12, [{ level: "warn", text: "Few sales" }]),
    stats("", true, 3, [{ level: "warn", text: "Parcels in no group" }]),
  ],
} as unknown as GroupsPreview;

describe("GroupChecks", () => {
  it("lists each group, Unassigned last, with its counts and what needs a look", () => {
    render(
      <GroupChecks
        groups={groups}
        preview={preview}
        unassignedColor="#999"
        edit={() => {}}
        setModeled={() => {}}
      />,
    );
    const rows = screen.getAllByRole("row").slice(1); // after the heading
    expect(rows.map((r) => within(r).getAllByRole("cell")[1]?.textContent)).toEqual([
      "Single family",
      "Condos",
      t.groups.unassigned,
    ]);
    const [sf, condo, none] = rows;
    expect(within(sf as HTMLElement).getByText("1,200")).toBeTruthy();
    expect(within(sf as HTMLElement).getByText("✓")).toBeTruthy(); // nothing to look at
    // Not modeled: said instead of its checks.
    expect(within(condo as HTMLElement).getByText(t.groups.notModeled)).toBeTruthy();
    expect(within(condo as HTMLElement).queryByText("Few sales")).toBeNull();
    // Unassigned has no Model it box, and shows its checks.
    expect(within(none as HTMLElement).queryByRole("checkbox")).toBeNull();
    expect(within(none as HTMLElement).getByText("Parcels in no group")).toBeTruthy();
  });

  it("ticks a group in or out of modelling, and goes back to the builder", () => {
    const setModeled = vi.fn();
    const edit = vi.fn();
    render(
      <GroupChecks
        groups={groups}
        preview={preview}
        unassignedColor="#999"
        edit={edit}
        setModeled={setModeled}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: `${t.groups.modelIt}: Single family` }));
    expect(setModeled).toHaveBeenCalledWith("sf", false);
    fireEvent.click(screen.getByRole("button", { name: t.groups.backToBuild }));
    expect(edit).toHaveBeenCalledOnce();
  });

  it("says it's loading until the counts come in", () => {
    render(
      <GroupChecks
        groups={groups}
        preview={undefined}
        unassignedColor="#999"
        edit={() => {}}
        setModeled={() => {}}
      />,
    );
    expect(screen.getByText(t.project.loading)).toBeTruthy();
  });
});
