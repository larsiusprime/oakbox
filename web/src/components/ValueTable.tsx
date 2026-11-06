import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { num } from "../lib/format";
import { t } from "../wording";
import { Val } from "./Val";

const v = t.wizard.values;

export type ValueSort = { by: "count" | "value"; desc: boolean } | null;

/** Clicking a heading sorts by it; again, the other way. Rows start most-first, values A→Z (and 1→9). */
export function nextSort(now: ValueSort, by: "count" | "value", natural: "count" | "value"): ValueSort {
  const current = now ?? { by: natural, desc: natural === "count" };
  return current.by === by ? { by, desc: !current.desc } : { by, desc: by === "count" };
}

/** Values with their row counts, as a table whose headings sort it (the sorting is the server's: lists are cut
 * short). natural: what the list is in before any heading is clicked. */
export function ValueTable({
  values,
  valueLabel,
  sort,
  natural = "count",
  onSort,
}: {
  values: { value: string; count: number }[];
  valueLabel?: string | undefined;
  sort: ValueSort;
  natural?: "count" | "value";
  onSort: (s: ValueSort) => void;
}) {
  const top = Math.max(1, ...values.map((x) => x.count));
  const shown = sort ?? { by: natural, desc: natural === "count" };
  const head = (by: "count" | "value", label: string, className: string) => {
    const on = shown.by === by;
    const Arrow = shown.desc ? ArrowDown : ArrowUp;
    return (
      <th className={className} aria-sort={on ? (shown.desc ? "descending" : "ascending") : "none"}>
        <button type="button" className="vals-sort" onClick={() => onSort(nextSort(sort, by, natural))}>
          {label}
          {/* Every sortable column shows it can be sorted: a faint ↕, the arrow once it's sorted by. */}
          {on ? (
            <Arrow aria-hidden="true" size="0.9em" />
          ) : (
            <ArrowUpDown aria-hidden="true" size="0.9em" className="sort-hint" />
          )}
        </button>
      </th>
    );
  };
  return (
    <div className="vals-scroll">
      <table className="vals-tbl">
        <thead>
          <tr>
            {head("value", valueLabel ?? v.value, "vals-th")}
            {head("count", v.rows, "vals-th vals-n")}
          </tr>
        </thead>
        <tbody>
          {values.map((x) => (
            <tr key={x.value}>
              <td className="vals-td mono vals-v">
                <Val v={x.value} />
              </td>
              <td className="vals-td vals-n">
                <span className="vals-bar" style={{ width: `${Math.max(2, (100 * x.count) / top)}%` }} />
                {num(x.count)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
