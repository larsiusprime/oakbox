import type { ModelGroup } from "../api/client";
import { NO_COLOUR } from "./colours";

/** A new model group named `name`: an id no other group has (from its name), and the first of `colors` none uses. */
export function newGroup(
  name: string,
  groups: ModelGroup[],
  colors: string[],
  conditions: ModelGroup["rule"]["conditions"] = [],
): ModelGroup {
  const base =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "") || "group";
  let id = base;
  for (let n = 2; groups.some((x) => x.id === id); n++) id = `${base}_${n}`;
  const used = new Set(groups.map((x) => x.color));
  const color = colors.find((c) => !used.has(c)) ?? colors[groups.length % colors.length] ?? NO_COLOUR;
  return { id, name, modeled: null, color, rule: { join: "any", conditions }, numeric: [], keys: [] };
}
