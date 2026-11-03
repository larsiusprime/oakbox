/** Model values › Small groups (SPEC F9, slice 2): a row per model group with the try's figures, why a group can't
 * be trusted, and for each flagged one, Leave unvalued or Model it anyway. */
import { useSetSmall, useSmallGroups } from "../api/models";
import { Seg } from "../components/Seg";
import { say, t } from "../copy";
import { num } from "../lib/format";

const s = t.values.small;
// A group's flag, said with its count and median ratio where the wording has them.
const flag = (f: string, n: number, median: string) => {
  const m = s.flags[f];
  return typeof m === "function" ? m({ n, median }) : m;
};

export function SmallGroupsStep({ projectId }: { projectId: string }) {
  const q = useSmallGroups(projectId);
  const set = useSetSmall(projectId);
  const v = q.data;
  if (!v) return <p className="empty">{q.error?.message ?? t.project.loading}</p>;
  if (!v.tried) return <p className="wiz-from">{s.notTried}</p>;
  const ratio = (x: number | null) => (x == null ? "—" : num(x, 3));
  return (
    <div className="cs-step">
      <table className="tbl sg-table">
        <thead>
          <tr>
            <th>{s.group}</th>
            <th className="cs-n">{s.parcels}</th>
            <th className="cs-n">{s.sales}</th>
            <th className="cs-n">{s.median}</th>
            <th className="cs-n">{s.cod}</th>
            <th className="cs-n">{s.belowZero}</th>
            <th>{s.fromTry}</th>
            <th>{s.todo}</th>
          </tr>
        </thead>
        <tbody>
          {v.groups.map((g) => (
            <tr key={g.id} className={g.modeled ? undefined : "not-modeled"}>
              <td>
                <span className="mg-sw ab-sw" style={{ background: g.color }} />
                {g.name}
              </td>
              <td className="cs-n">{num(g.parcels)}</td>
              <td className="cs-n">{num(g.sales)}</td>
              <td className="cs-n">{g.modeled ? ratio(g.median) : ""}</td>
              <td className="cs-n">{g.modeled && g.cod != null ? num(g.cod, 1) : g.modeled ? "—" : ""}</td>
              <td className="cs-n">{g.modeled ? num(g.below_zero) : ""}</td>
              <td>
                {!g.modeled ? (
                  <span className="wiz-from">{s.notModeled}</span>
                ) : g.flags.length === 0 ? (
                  <span className="rv-cell-pill">
                    <span className="pill pill-ok">✓ {s.fine}</span>
                  </span>
                ) : (
                  <span className="rv-cell-pill sg-flags">
                    {g.flags.map((f) => (
                      <span key={f} className={f === "no_holdout" ? "pill pill-warn" : "pill pill-bad"}>
                        {f === "no_holdout" ? "!" : "✗"}{" "}
                        {flag(f, f === "below_zero" ? g.below_zero : g.sales, ratio(g.median))}
                      </span>
                    ))}
                  </span>
                )}
              </td>
              <td>
                {g.choice ? (
                  <Seg
                    label={`${s.todo}: ${g.name}`}
                    value={g.choice}
                    options={[
                      ["leave", s.leave],
                      ["model", s.model],
                    ]}
                    disabled={g.can_model ? [] : ["model"]}
                    titles={g.can_model ? {} : { model: s.cantModel }}
                    onChange={(choice) => set.mutate({ group: g.id, choice })}
                  />
                ) : g.modeled ? (
                  <span className="wiz-from">{s.modeled}</span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={v.unvalued.length ? "wiz-warn" : "wiz-ok"}>
        {v.unvalued.length ? say.values.small.unvalued(v.unvalued_parcels, v.unvalued) : s.noneUnvalued}
      </p>
      {v.blanked > 0 && <p className="wiz-warn">{s.blanked({ n: v.blanked })}</p>}
      {set.error && (
        <p className="error" role="alert">
          {set.error.message}
        </p>
      )}
      <p className="wiz-from">
        {s.neverBelow} {s.applies}
      </p>
    </div>
  );
}
