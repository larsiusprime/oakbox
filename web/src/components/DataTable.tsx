import { type ReactNode, useRef, useState } from "react";
import { InfoTip } from "./Tip";

export type Column<R> = {
  key: string;
  label: string;
  tip?: string;
  /** What the column sorts by; blanks sort last either way. */
  value: (row: R) => number | string | null | undefined;
  /** The cell; the value as it is if not given. */
  cell?: (row: R) => ReactNode;
  numeric?: boolean;
  /** Starting width in pixels. */
  width?: number;
};

type Sort = { key: string; desc: boolean } | null;

const MIN = 48;

function widthsKey(id: string) {
  return `oakbox.columns.${id}`;
}

function savedWidths(id: string): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(widthsKey(id)) ?? "{}");
  } catch {
    return {};
  }
}

/** A table whose headings sort it (again, the other way; a third time, back as it came) and whose column edges
 * can be dragged to resize them. Widths are remembered per table id, on this computer. */
export function DataTable<R>({
  id,
  columns,
  rows,
  rowKey,
  rowClass,
  caption,
}: {
  id: string;
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R) => string;
  rowClass?: (row: R) => string | undefined;
  caption?: string;
}) {
  const [sort, setSort] = useState<Sort>(null);
  const [widths, setWidths] = useState<Record<string, number>>(() => savedWidths(id));
  const drag = useRef<{ key: string; x: number; w: number } | null>(null);

  const sorted = sort
    ? [...rows].sort(
        compare(
          columns.find((c) => c.key === sort.key),
          sort.desc,
        ),
      )
    : rows;
  const next = (key: string): Sort =>
    sort?.key !== key ? { key, desc: false } : sort.desc ? null : { key, desc: true };

  const start = (key: string, e: React.PointerEvent<HTMLSpanElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const th = e.currentTarget.parentElement as HTMLElement;
    drag.current = { key, x: e.clientX, w: th.getBoundingClientRect().width };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const move = (e: React.PointerEvent<HTMLSpanElement>) => {
    const d = drag.current;
    if (!d) return;
    setWidths((w) => ({ ...w, [d.key]: Math.max(MIN, Math.round(d.w + e.clientX - d.x)) }));
  };
  const end = () => {
    if (!drag.current) return;
    drag.current = null;
    setWidths((w) => {
      try {
        localStorage.setItem(widthsKey(id), JSON.stringify(w));
      } catch {
        // Not remembered: the widths still hold until the page is left.
      }
      return w;
    });
  };

  return (
    <div className="dt-wrap">
      <table className="bi-tbl cs-tbl dt">
        {caption && <caption className="dt-caption">{caption}</caption>}
        <colgroup>
          {columns.map((c) => {
            const w = widths[c.key] ?? c.width;
            return <col key={c.key} style={w ? { width: `${w}px` } : undefined} />;
          })}
        </colgroup>
        <thead>
          <tr>
            {columns.map((c) => {
              const on = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  className={c.numeric ? "cs-n dt-th" : "dt-th"}
                  aria-sort={on ? (sort.desc ? "descending" : "ascending") : "none"}
                >
                  <button type="button" className="vals-sort dt-sort" onClick={() => setSort(next(c.key))}>
                    {c.tip ? <InfoTip label={c.label} text={c.tip} /> : c.label}
                    <span className="dt-arrow" aria-hidden="true">
                      {on ? (sort.desc ? "▼" : "▲") : ""}
                    </span>
                  </button>
                  <span
                    className="dt-grip"
                    onPointerDown={(e) => start(c.key, e)}
                    onPointerMove={move}
                    onPointerUp={end}
                    onPointerCancel={end}
                  />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={rowKey(r)} className={rowClass?.(r)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "cs-n" : undefined}>
                  {c.cell ? c.cell(r) : (c.value(r) ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function compare<R>(c: Column<R> | undefined, desc: boolean) {
  return (a: R, b: R) => {
    if (!c) return 0;
    const x = c.value(a);
    const y = c.value(b);
    if (x == null || x === "") return y == null || y === "" ? 0 : 1;
    if (y == null || y === "") return -1;
    const d = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return desc ? -d : d;
  };
}
