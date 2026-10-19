import { CircleCheck, CircleHelp, CircleX } from "lucide-react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import type { GroupStudy, Stat, ValueStudy } from "../api/client";
import { fmt, fmtRange, type Verdict, verdict } from "../stats";
import { t } from "../strings";

type Metric = "medianRatio" | "cod" | "prd" | "prb";

function Explain({ label, text }: { label: string; text: string }) {
  return (
    <DialogTrigger>
      <Button className="explain-button" aria-label={`What is ${label}?`}>
        <CircleHelp aria-hidden="true" size="1em" />
      </Button>
      <Popover className="popover" placement="top">
        <Dialog className="popover-body">{text}</Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function Mark({ v }: { v: Verdict }) {
  if (v === "unknown") return null;
  const Icon = v === "meets" ? CircleCheck : CircleX;
  return (
    <span className={`mark mark-${v}`}>
      <Icon aria-hidden="true" size="1em" strokeWidth={2.5} />
      {v === "meets" ? t.results.meets : t.results.outside}
    </span>
  );
}

function Cell({ stat, metric, digits }: { stat: Stat | null | undefined; metric: Metric; digits: number }) {
  return (
    <td>
      <span className="stat-value">{fmt(stat?.value, digits)}</span>
      <span className="stat-range">{fmtRange(stat, digits)}</span>
      <Mark v={verdict(stat, metric)} />
    </td>
  );
}

function Row({ name, g, overall }: { name: string; g: GroupStudy; overall?: boolean }) {
  const r = g.ratio;
  return (
    <tr className={overall ? "row-overall" : undefined}>
      <th scope="row">{name}</th>
      <td className="num">{r.count.toLocaleString()}</td>
      {r.count < 5 ? (
        <td colSpan={5} className="note">
          {t.results.notEnough}
        </td>
      ) : (
        <>
          <Cell stat={r.median_ratio} metric="medianRatio" digits={2} />
          <Cell stat={r.cod} metric="cod" digits={1} />
          <Cell stat={r.prd} metric="prd" digits={3} />
          <Cell stat={g.vertical?.prb} metric="prb" digits={3} />
          <td>
            <span className="stat-value">{fmt(g.vertical?.vei, 1)}</span>
          </td>
        </>
      )}
    </tr>
  );
}

export function ValueStudyTable({ study }: { study: ValueStudy }) {
  const r = t.results;
  const metrics = [
    { key: "medianRatio", label: r.medianRatio },
    { key: "cod", label: r.cod },
    { key: "prd", label: r.prd },
    { key: "prb", label: r.prb },
    { key: "vei", label: r.vei },
  ] as const;
  const groups = Object.entries(study.groups);
  return (
    <section className="panel results" aria-labelledby={`results-${study.field}`}>
      <header className="panel-head">
        <h2 id={`results-${study.field}`}>{r.title}</h2>
        <span className="panel-meta">
          {r.window(study.window.start ?? "", study.window.end ?? "", study.overall.ratio.count)}
        </span>
      </header>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{r.group}</th>
              <th scope="col" className="num">
                {r.sales}
              </th>
              {metrics.map((m) => (
                <th scope="col" key={m.key}>
                  <span className="th-label">
                    {m.label} <Explain label={m.label} text={r.explain[m.key]} />
                  </span>
                  <span className="th-target">
                    {r.target}: {r.targets[m.key]}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <Row name={r.overall} g={study.overall} overall />
            {groups.length > 1 && groups.map(([name, g]) => <Row key={name} name={name} g={g} />)}
          </tbody>
        </table>
      </div>
      <p className="footnote">{r.targetsNote}</p>
    </section>
  );
}
