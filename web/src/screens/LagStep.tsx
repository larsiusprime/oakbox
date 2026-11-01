/** Variables › Nearby sales and buildings (OpenAVMKit's spatial lag, SPEC F9): each parcel gets the distance-weighted
 * average of its nearest sales' prices and of its nearest parcels' characteristics, as variables. On by default; each
 * model group averages its own sales, and may borrow another group's; fields besides OpenAVMKit's own, none to start. */

import type { ModelSetup } from "../api/client";
import { Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { t } from "../strings";

const l = t.values.lag;

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
  }) => void;
}) {
  const v = setup.lag;
  const names = Object.fromEntries(v.groups.map((g) => [g.id, g.name]));
  return (
    <div className="lag">
      <Tick isSelected={v.on} onChange={(on) => set({ lag_on: on })}>
        {l.on}
      </Tick>
      <p className="wiz-from">{l.how}</p>
      {v.on && (
        <>
          <div className="lag-fields">
            <span className="mo-label">{l.own}</span>
            <MultiPick
              label={l.own}
              values={v.own.map((x) => ({ value: x.field, label: x.name }))}
              chosen={v.chosen}
              onChange={(lag_own) => set({ lag_own })}
              placeholder={l.noOwn}
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
            />
            <span className="wiz-from">{l.fieldsWhy}</span>
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
                  <td className="num">{g.sales.toLocaleString()}</td>
                  <td>
                    <MultiPick
                      label={l.borrowFor(g.name)}
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
                        {l.plusOwn(g.borrow.map((x) => names[x] ?? x).join(", "))}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="wiz-from">{l.split}</p>
        </>
      )}
    </div>
  );
}
