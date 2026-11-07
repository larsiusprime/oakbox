/** Variables › Per area statistics (OpenAVMKit's area statistics, SPEC §3.12.3): each parcel gets its area's figures
 * (the median sale price of its census tract…) as variables. The cousin of Spatial average statistics, by named areas.
 * Off to start: what turning it on gives is shown faded, as it would start. */
import { useState } from "react";
import type { ModelSetup } from "../api/client";
import { Field, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { WarnChip } from "../components/WarnChip";
import { num } from "../lib/format";
import { t } from "../wording";

const a = t.values.area;
type Area = ModelSetup["area"];
type RowId = Area["rows"][number]["id"];
type Stat = Area["stats"][number];
const STATS: Stat[] = ["median", "mean", "std", "p25", "p75", "min", "max"];

export function AreaStep({
  setup,
  set,
}: {
  setup: ModelSetup;
  set: (body: {
    area_on?: boolean;
    area_stats?: Stat[];
    area_min_count?: number;
    area_ticks?: Record<string, RowId[]>;
  }) => void;
}) {
  const v = setup.area;
  // Blank under: typed freely, kept on leaving the box when it's a whole number from 1 to 1,000.
  const [draft, setDraft] = useState<string | null>(null);
  const keepMin = () => {
    const n = Number(draft);
    if (draft !== null && Number.isInteger(n) && n >= 1 && n <= 1000 && n !== v.min_count)
      set({ area_min_count: n });
    setDraft(null);
  };
  const tick = (location: string, row: RowId, on: boolean) => {
    const all = Object.fromEntries(v.locations.map((l) => [l.location, l.ticks]));
    const now = all[location] ?? [];
    all[location] = on ? [...now, row] : now.filter((r) => r !== row);
    set({ area_ticks: all });
  };
  const part = (p: "sales" | "parcels") => v.rows.filter((r) => r.part === p);
  const section = (title: string, rows: Area["rows"]) =>
    rows.length > 0 && (
      <>
        <tr className="area-sec">
          <td colSpan={v.locations.length + 1}>{title}</td>
        </tr>
        {rows.map((r) => (
          <tr key={r.id}>
            <td>{cap(r.name)}</td>
            {v.locations.map((l) => (
              <td key={l.location} className="area-c">
                <Tick isSelected={l.ticks.includes(r.id)} onChange={(on) => tick(l.location, r.id, on)}>
                  <span className="visually-hidden">{a.tickFor({ row: r.name, location: l.name })}</span>
                </Tick>
              </td>
            ))}
          </tr>
        ))}
      </>
    );
  return (
    <div className="area">
      <Tick isSelected={v.on} onChange={(on) => set({ area_on: on })}>
        {a.on}
      </Tick>
      {v.locations.length === 0 ? (
        <p className="wiz-from">{a.noLocations}</p>
      ) : (
        // Off: everything as it would start, faded and out of reach (inert), so turning it on gives what's shown.
        <div className={v.on ? "area-body" : "area-body area-off"} inert={!v.on}>
          {/* Labels in one column, what's set in the next (the number box's own label is read aloud, not shown). */}
          <div className="area-set">
            <span className="mo-label">{a.figures}</span>
            <MultiPick
              label={a.figures}
              values={STATS.map((s) => ({ value: s, label: a.stats[s] }))}
              chosen={v.stats}
              onChange={(x) => set({ area_stats: x as Stat[] })}
              placeholder={a.noFigures}
            />
            <span className="mo-label" aria-hidden="true">
              {a.blankUnder}
            </span>
            <span className="area-min">
              <Field
                label={a.blankUnder}
                type="number"
                width="short"
                value={draft ?? String(v.min_count)}
                onChange={setDraft}
                onBlur={keepMin}
              />
              <span className="wiz-from">{a.blankUnderUnit}</span>
            </span>
          </div>
          <table className="tbl area-grid">
            <thead>
              <tr>
                <th />
                {v.locations.map((l) => (
                  <th key={l.location} className="area-c">
                    {l.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {section(a.fromSales, part("sales"))}
              {section(a.fromParcels, part("parcels"))}
              <tr className="area-sec">
                <td colSpan={v.locations.length + 1}>{a.theAreas}</td>
              </tr>
              <tr>
                <td>{a.areas}</td>
                {v.locations.map((l) => (
                  <td key={l.location} className="area-c">
                    {num(l.areas)}
                  </td>
                ))}
              </tr>
              <tr>
                <td>{a.typical}</td>
                {v.locations.map((l) => (
                  <td key={l.location} className="area-c">
                    {num(l.typical_sales)}
                  </td>
                ))}
              </tr>
              <tr>
                <td>{a.under}</td>
                {v.locations.map((l) => (
                  <td key={l.location} className="area-c">
                    {l.under > 0 ? (
                      <WarnChip title={a.underChip({ n: l.under })}>
                        <p>{a.underTip({ min: v.min_count, parcels: l.parcels_under })}</p>
                        <p className="wiz-from">{l.under_names.join(", ")}</p>
                      </WarnChip>
                    ) : (
                      "—"
                    )}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
          <p className="wiz-from">{a.adds({ n: v.adds })}</p>
        </div>
      )}
    </div>
  );
}

function cap(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
