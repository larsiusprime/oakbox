import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import type { GroupStudy, ValueStudy } from "../api/client";
import { fmt, fmtRange, type Verdict, verdict } from "../stats";
import { t } from "../strings";

function Explain({ label, text }: { label: string; text: string }) {
  return (
    <DialogTrigger>
      <Button className="explain-button" aria-label={`What is ${label}?`}>
        ?
      </Button>
      <Popover className="popover" placement="top">
        <Dialog className="popover-body">{text}</Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function Badge({ v }: { v: Verdict }) {
  if (v === "unknown") return null;
  return (
    <span className={`badge badge-${v}`}>
      <span aria-hidden="true">{v === "meets" ? "✓ " : "✗ "}</span>
      {v === "meets" ? t.results.meets : t.results.outside}
    </span>
  );
}

function Row({ name, g, strong }: { name: string; g: GroupStudy; strong?: boolean }) {
  if (g.ratio.count < 5) {
    return (
      <tr className={strong ? "row-strong" : undefined}>
        <th scope="row">{name}</th>
        <td className="num">{g.ratio.count.toLocaleString()}</td>
        <td colSpan={5} className="muted">
          {t.results.notEnough}
        </td>
      </tr>
    );
  }
  const v = g.vertical;
  return (
    <tr className={strong ? "row-strong" : undefined}>
      <th scope="row">{name}</th>
      <td className="num">{g.ratio.count.toLocaleString()}</td>
      <td>
        <div className="stat">
          <span className="stat-value">{fmt(g.ratio.median_ratio.value)}</span>
          <span className="stat-range">{fmtRange(g.ratio.median_ratio)}</span>
          <Badge v={verdict(g.ratio.median_ratio, "medianRatio")} />
        </div>
      </td>
      <td>
        <div className="stat">
          <span className="stat-value">{fmt(g.ratio.cod.value, 1)}</span>
          <span className="stat-range">{fmtRange(g.ratio.cod, 1)}</span>
          <Badge v={verdict(g.ratio.cod, "cod")} />
        </div>
      </td>
      <td>
        <div className="stat">
          <span className="stat-value">{fmt(g.ratio.prd.value, 3)}</span>
          <span className="stat-range">{fmtRange(g.ratio.prd, 3)}</span>
          <Badge v={verdict(g.ratio.prd, "prd")} />
        </div>
      </td>
      <td>
        <div className="stat">
          <span className="stat-value">{fmt(v?.prb.value, 3)}</span>
          <span className="stat-range">{fmtRange(v?.prb, 3)}</span>
          <Badge v={verdict(v?.prb, "prb")} />
        </div>
      </td>
      <td>
        <div className="stat">
          <span className="stat-value">{fmt(v?.vei, 1)}</span>
        </div>
      </td>
    </tr>
  );
}

export function ValueStudyTable({ study }: { study: ValueStudy }) {
  const r = t.results;
  return (
    <section className="panel results" aria-labelledby={`results-${study.field}`}>
      <h3 id={`results-${study.field}`}>{r.title}</h3>
      <p className="muted">{r.window(study.window.start ?? "", study.window.end ?? "")}</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{r.group}</th>
              <th scope="col" className="num">
                {r.sales}
              </th>
              <th scope="col">
                {r.medianRatio} <Explain label={r.medianRatio} text={r.explain.medianRatio} />
              </th>
              <th scope="col">
                {r.cod} <Explain label={r.cod} text={r.explain.cod} />
              </th>
              <th scope="col">
                {r.prd} <Explain label={r.prd} text={r.explain.prd} />
              </th>
              <th scope="col">
                {r.prb} <Explain label={r.prb} text={r.explain.prb} />
              </th>
              <th scope="col">
                {r.vei} <Explain label={r.vei} text={r.explain.vei} />
              </th>
            </tr>
          </thead>
          <tbody>
            <Row name={r.overall} g={study.overall} strong />
            {Object.keys(study.groups).length > 1 &&
              Object.entries(study.groups).map(([name, g]) => <Row key={name} name={name} g={g} />)}
          </tbody>
        </table>
      </div>
      <p className="footnote">{r.targetsNote}</p>
    </section>
  );
}
