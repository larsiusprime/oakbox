/** Model values › Model values (SPEC F9, slice 2): the finalized values against the sales, as Check my values judges
 * the roll's, on the set of sales chosen (out of fold, held out, as valued), the roll's beside them on the same
 * sales; then what every parcel got. */
import { useState } from "react";
import type { components } from "../api/schema";
import { Seg } from "../components/Seg";
import { InfoTip } from "../components/Tip";
import { moneyShort, num, signed } from "../lib/format";
import { t } from "../wording";
import { FinalMap } from "./FinalMap";
import { Scorecard } from "./ValueTables";

type Receipt = components["schemas"]["FinalReceipt"];
type SetKey = Receipt["sets"][number]["key"];
const f = t.values.final;

export function FinalValues({
  projectId,
  receipt,
  currency,
  units,
}: {
  projectId: string;
  receipt: Receipt;
  currency: string;
  units: string;
}) {
  const have = receipt.sets.filter((x) => x.model);
  const [key, setKey] = useState<SetKey>(have[0]?.key ?? "oof");
  const set = receipt.sets.find((x) => x.key === key);
  const empty = receipt.sets.filter((x) => !x.model).map((x) => x.key);
  const valued = receipt.groups.reduce((a, g) => a + g.valued, 0);
  const parcels = receipt.groups.reduce((a, g) => a + g.parcels, 0);
  return (
    <div className="fv">
      <div className="fv-on">
        <span className="mo-label">{f.judgedOn}</span>
        <Seg
          label={f.judgedOn}
          value={key}
          options={receipt.sets.map((x) => [x.key, f.sets[x.key] ?? x.key] as const)}
          onChange={setKey}
          disabled={empty}
          titles={Object.fromEntries(empty.map((k) => [k, f.noSales({ set: f.sets[k] ?? k })]))}
        />
      </div>
      <p className="wiz-from">{f.setWhy[key]}</p>
      {set?.model ? (
        <>
          <p className="wiz-from">{f.window({ n: set.sales, start: receipt.start, end: receipt.end })}</p>
          <h3 className="fv-h">{f.models}</h3>
          <Scorecard groups={[...set.model.groups, set.model.overall]} technical />
          {receipt.roll && set.roll ? (
            <>
              <h3 className="fv-h">{f.roll({ name: receipt.roll })}</h3>
              <Scorecard groups={[...set.roll.groups, set.roll.overall]} technical />
            </>
          ) : (
            !receipt.roll && <p className="wiz-from">{f.noRoll}</p>
          )}
        </>
      ) : (
        <p className="wiz-from">{f.noSales({ set: f.sets[key] ?? key })}</p>
      )}
      <h3 className="fv-h">{f.map.head}</h3>
      <FinalMap projectId={projectId} receipt={receipt} which={key} currency={currency} units={units} />
      <h3 className="fv-h">{f.groupsHead}</h3>
      <p className="wiz-from">{f.totals({ valued, parcels })}</p>
      <table className="tbl fv-groups">
        <thead>
          <tr>
            <th>{f.group}</th>
            <th className="cs-n">{f.parcels}</th>
            <th className="cs-n">{f.valued}</th>
            {receipt.roll && (
              <>
                <th className="cs-n">
                  <InfoTip label={f.change} text={f.changeWhy} />
                </th>
                <th className="cs-n">{f.up}</th>
                <th className="cs-n">{f.down}</th>
              </>
            )}
            <th className="cs-n">{f.total}</th>
            {receipt.roll && <th className="cs-n">{f.rollTotal}</th>}
          </tr>
        </thead>
        <tbody>
          {receipt.groups.map((g) => (
            <tr key={g.id} className={g.valued ? undefined : "not-modeled"}>
              <td>
                <span className="mg-sw ab-sw" style={{ background: g.color }} />
                {g.name}
                {g.blanked > 0 && <span className="wiz-from"> · {f.belowZero({ n: g.blanked })}</span>}
              </td>
              <td className="cs-n">{num(g.parcels)}</td>
              {g.unvalued ? (
                <td colSpan={receipt.roll ? 6 : 2} className="wiz-from">
                  {g.unvalued}
                </td>
              ) : (
                <>
                  <td className="cs-n">{num(g.valued)}</td>
                  {receipt.roll && (
                    <>
                      <td className="cs-n">
                        {g.median_change == null ? "—" : `${signed(100 * g.median_change, 1)}%`}
                      </td>
                      <td className="cs-n">{num(g.up)}</td>
                      <td className="cs-n">{num(g.down)}</td>
                    </>
                  )}
                  <td className="cs-n">{moneyShort(g.total, currency)}</td>
                  {receipt.roll && <td className="cs-n">{moneyShort(g.roll_total, currency)}</td>}
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {receipt.notes.length > 0 && (
        <details className="fv-notes">
          <summary>{f.notes}</summary>
          <ul>
            {receipt.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
