import { Button } from "react-aria-components";
import type { GroupsPreview, ModelGroup } from "../api/client";
import { Tick } from "../components/Form";
import { ShowOnMapButton } from "../components/ShowOnMap";
import { InfoTip } from "../components/Tip";
import { LoadingBar } from "../components/Waiting";
import { num } from "../lib/format";
import { t } from "../wording";

const g = t.groups;

/** Each saved group's parcels and sales, with what needs a look; Unassigned last. */
export function GroupChecks({
  groups,
  preview: p,
  unassignedColor,
  setModeled,
  onMap,
}: {
  groups: ModelGroup[];
  preview: GroupsPreview | undefined;
  unassignedColor: string;
  setModeled: (id: string, modeled: boolean) => void;
  /** The group shown alone on the map ("" Unassigned, null every group), and showing one. */
  onMap?: { shown: string | null; show: (id: string) => void };
}) {
  if (!p) return <LoadingBar />;
  const rows = [
    ...groups.map((x) => [x.id, x.name, x.color] as const),
    ["", g.unassigned, unassignedColor] as const,
  ];
  return (
    <>
      <table className="tbl mg-checks">
        <thead>
          <tr>
            <th className="mg-model">
              <InfoTip label={g.modelIt} text={g.modelItTip} />
            </th>
            <th>{g.run.group}</th>
            <th className="cs-n">{g.run.parcels}</th>
            <th className="cs-n">{g.run.sales}</th>
            <th className="cs-n">{g.run.vacantSales}</th>
            <th>{g.checksCol}</th>
            {onMap && <th />}
          </tr>
        </thead>
        <tbody>
          {rows.map(([id, name, color]) => {
            const x = p.stats.find((s) => s.id === id);
            if (!x) return null;
            const look = x.checks.filter((c) => c.level !== "ok");
            const off = id !== "" && !x.modeled;
            return (
              <tr key={id || "unassigned"} className={off ? "not-modeled" : undefined}>
                <td className="mg-model">
                  {id !== "" && (
                    <Tick isSelected={x.modeled} onChange={(on) => setModeled(id, on)}>
                      <span className="sr-only">{`${g.modelIt}: ${name}`}</span>
                    </Tick>
                  )}
                </td>
                <td>
                  <span className="mg-sw ab-sw" style={{ background: color }} />
                  {name}
                </td>
                <td className="cs-n">{num(x.parcels)}</td>
                <td className="cs-n">{num(x.sales)}</td>
                <td className="cs-n">{num(x.vacant_sales)}</td>
                <td>
                  {off ? (
                    g.notModeled
                  ) : look.length === 0 ? (
                    <span className="wiz-ok">✓</span>
                  ) : (
                    look.map((c) => (
                      <div key={c.text} className={`mg-check ${c.level}`}>
                        {c.text}
                      </div>
                    ))
                  )}
                </td>
                {onMap && (
                  <td className="rv-onmap">
                    <ShowOnMapButton shown={onMap.shown === id} onPress={() => onMap.show(id)} />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
