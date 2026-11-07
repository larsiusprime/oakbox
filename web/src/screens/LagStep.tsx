/** Variables › Spatial average statistics (OpenAVMKit's spatial lag, SPEC F9): each parcel gets the distance-weighted
 * average of its nearest sales' prices and of its nearest parcels' characteristics, as variables. On by default; each
 * model group averages its own sales, and may borrow another group's; fields besides OpenAVMKit's own, none to start. */

import { useState } from "react";
import type { ModelSetup } from "../api/client";
import { Field, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { num } from "../lib/format";
import { say, t } from "../wording";

const l = t.values.lag;

/** An average's name without "Nearby", which this step says once for all of them: "Finished area". As variables, in
 * the lists, they keep it ("Nearby finished area"), beside the parcel's own. */
function plain(name: string): string {
  const rest = name.replace(/^Nearby /, "");
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

export function LagStep({
  setup,
  set,
}: {
  setup: ModelSetup;
  set: (body: {
    lag_on?: boolean;
    lag_borrow?: { group: string; sources: string[] };
    lag_fields?: string[];
    lag_own?: string[];
    lag_k?: number;
  }) => void;
}) {
  const v = setup.lag;
  const names = Object.fromEntries(v.groups.map((g) => [g.id, g.name]));
  // How many nearest: typed freely, kept on leaving the box when it's a whole number from 1 to 50.
  const [draft, setDraft] = useState<string | null>(null);
  const keepK = () => {
    const n = Number(draft);
    if (draft !== null && Number.isInteger(n) && n >= 1 && n <= 50 && n !== v.k) set({ lag_k: n });
    setDraft(null);
  };
  return (
    <div className="lag">
      <Tick isSelected={v.on} onChange={(on) => set({ lag_on: on })}>
        {l.on}
      </Tick>
      <p className="wiz-from">{l.how}</p>
      {v.on && (
        <>
          {/* Labels in one column, what's set in the next, why in the third. */}
          <div className="lag-grid">
            <div className="lag-fields lag-k">
              <Field
                label={l.nearest}
                type="number"
                width="short"
                value={draft ?? String(v.k)}
                onChange={setDraft}
                onBlur={keepK}
              />
              <span className="wiz-from">{l.nearestWhy({ k: v.k })}</span>
            </div>
            <div className="lag-fields">
              <span className="mo-label">{l.own}</span>
              <MultiPick
                label={l.own}
                values={v.own.map((x) => ({ value: x.field, label: plain(x.name) }))}
                chosen={v.chosen}
                onChange={(lag_own) => set({ lag_own })}
                placeholder={l.noOwn}
                brief
              />
              <span className="wiz-from">{l.ownWhy}</span>
            </div>
            <div className="lag-fields">
              <span className="mo-label">{l.fields}</span>
              <MultiPick
                label={l.fields}
                values={v.offered.map((x) => ({ value: x.field, label: x.name }))}
                chosen={v.fields}
                onChange={(lag_fields) => set({ lag_fields })}
                placeholder={l.noFields}
                brief
              />
              <span className="wiz-from">{l.fieldsWhy}</span>
            </div>
          </div>
          <table className="tbl lag-groups">
            <thead>
              <tr>
                <th>{l.group}</th>
                <th className="num">{l.sales}</th>
                <th>{l.averages}</th>
              </tr>
            </thead>
            <tbody>
              {v.groups.map((g) => (
                <tr key={g.id}>
                  <td>
                    <span className="mg-sw ab-sw" style={{ background: g.color }} /> {g.name}
                  </td>
                  <td className="num">{num(g.sales)}</td>
                  <td>
                    <MultiPick
                      label={l.borrowFor({ group: g.name })}
                      values={v.groups
                        .filter((x) => x.id !== g.id)
                        .map((x) => ({ value: x.id, label: x.name, count: x.sales }))}
                      chosen={g.borrow}
                      onChange={(sources) => set({ lag_borrow: { group: g.id, sources } })}
                      placeholder={l.ownOnly}
                      countNoun={l.salesNoun}
                    />
                    {g.borrow.length > 0 && (
                      <span className="wiz-from">
                        {" "}
                        {l.plusOwn({ others: g.borrow.map((x) => names[x] ?? x).join(", ") })}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="wiz-from">{say.values.lag.split(v.k)}</p>
        </>
      )}
    </div>
  );
}
