import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { Button, Radio, RadioGroup } from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type FieldResult,
  type RatioPatch,
  type RatioSetup,
  type RatioStudy,
  type RatioTargets,
  type RatioView,
  unwrap,
} from "../api/client";
import { stepKey, useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { addBasemap } from "../components/basemap";
import { Choice, Field, Tick } from "../components/Form";
import { Pill, type Verdict, verdictOf } from "../components/Pill";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { InfoTip } from "../components/Tip";
import { day, money, num, signed, when } from "../lib/format";
import { useWidth } from "../lib/hooks";
import { t } from "../strings";

const r = t.ratio;
type RStep =
  | "sales"
  | "standards"
  | "run"
  | "summary"
  | "groups"
  | "prices"
  | "map"
  | "regions"
  | "similar"
  | "extreme";
const STEPS: RStep[] = [
  "sales",
  "standards",
  "run",
  "summary",
  "groups",
  "prices",
  "map",
  "regions",
  "similar",
  "extreme",
];
const AFTER: RStep[] = ["summary", "groups", "prices", "map", "regions", "similar", "extreme"];
type Class = RatioSetup["groups"][number]["cls"];

/** Whether Looks right was pressed on an up-to-date Check my values. */
export function useValuesChecked(projectId: string): boolean {
  return useStep("ratio", projectId).data?.accepted ?? false;
}

const ratioText = (v: number | null | undefined) => num(v, 3);
const pct = (v: number) => Math.round(100 * v);

/** The PRB's verdict: met within the good range, missed outside the unacceptable, near in between. */
function prbVerdict(g: RatioStudy): Verdict | null {
  const ok = g.verdict?.prb;
  if (ok != null) return verdictOf(ok);
  return g.verdict?.judged && g.prb != null ? "slight" : null;
}

/** Step 4, Check my values (SPEC F8): the values on the roll against what parcels sold for, judged against the
 * IAAO's targets (or the user's), one task at a time. */
export function CheckValuesTab({ projectId, currency }: { projectId: string; currency: string }) {
  const state = useStep("ratio", projectId);
  const v = state.data;
  const { setup, change } = useStepSetup("ratio", projectId, !!v && v.blocked.length === 0);
  const act = useStepAct("ratio", projectId);
  const nav = useStepNav<RStep>();
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  const running = v.status === "running";
  const rc = v.receipt;
  const fresh = !!rc && !v.stale;
  const fallback: RStep = running ? "run" : fresh ? "summary" : rc ? "run" : "sales";
  const current = nav.current(v.status, fallback, "summary");
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
  // Only the market value is checked (one result).
  const result: FieldResult | undefined = rc?.results[0];
  const nominal = result?.trimmed.filter((x) => x.nominal) ?? [];
  const called = rc ? (v.stale ? "attention" : "done") : "blank";
  const steps: Step[] = STEPS.map((key) => ({
    key,
    title: r.steps[key],
    status: AFTER.includes(key)
      ? !rc
        ? "blank"
        : key === "extreme" && nominal.length
          ? "attention"
          : key === "extreme" && v.accepted
            ? "done"
            : "blank"
      : key === "run"
        ? called
        : key === "sales" && setup.data && setup.data.year_before === 0
          ? "attention"
          : setup.data
            ? "done"
            : "blank",
    disabled: AFTER.includes(key) && !rc,
  }));
  const i = STEPS.indexOf(current);
  const prev = STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  const toValues = () => navigate({ name: "project", id: projectId, tab: "values" });
  const onward = { label: t.wizard.next, onPress: () => go(STEPS[i + 1] ?? current) };
  const u = setup.data;
  const set = (body: RatioPatch) => change.mutate(body);
  const errors = [change.error, act.error, setup.error].map(
    (e) =>
      e && (
        <p key={e.message} className="error" role="alert">
          {e.message}
        </p>
      ),
  );
  if (v.blocked.length)
    return (
      <StepFrame steps={steps} current="sales" go={() => {}}>
        <StepBody kicker={r.kicker} title={r.sales.title}>
          <div className="bi-warn">
            <b>{r.blocked}</b> {v.blocked[0]}
          </div>
        </StepBody>
      </StepFrame>
    );
  const loading = <p className="empty">{t.project.loading}</p>;

  return (
    <StepFrame steps={steps} current={current} go={go}>
      {current === "sales" && (
        <>
          <StepBody kicker={r.kicker} title={r.sales.title} lede={r.sales.lede}>
            {u ? <SalesCard key={`${u.start}|${u.end}`} v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot next={onward} />
        </>
      )}
      {current === "standards" && (
        <>
          <StepBody kicker={r.kicker} title={r.standards.title} lede={r.standards.lede}>
            {u ? <StandardsCard v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "run" && (
        <>
          <StepBody kicker={r.kicker} title={r.steps.run} lede={r.run.lede}>
            {running ? (
              <RunProgress job={v.job} lastSeconds={rc?.seconds ?? null} />
            ) : (
              <>
                {v.status === "failed" && v.job?.error && (
                  <p className="error" role="alert">
                    {t.bringIn.failed} <span className="mono">{v.job.error}</span>
                  </p>
                )}
                {v.stale && <p className="wiz-warn">{r.run.stale}</p>}
                {fresh && rc && <p className="wiz-ok">{r.run.ran(when(rc.ran_at), rc.seconds)}</p>}
                {!rc && <p className="wiz-from">{t.bringIn.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: r.run.again, onPress: runIt }] : []}
            next={
              running
                ? { label: t.bringIn.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? onward
                  : { label: rc ? r.run.againNext : r.run.next, disabled: act.isPending, onPress: runIt }
            }
          />
        </>
      )}
      {AFTER.includes(current) && rc && result && (
        <>
          <StepBody kicker={r.kicker} {...(current === "prices" ? {} : { title: r.steps[current] })}>
            {v.stale && <p className="wiz-warn">{r.run.stale}</p>}
            {current === "summary" && (
              <Summary result={result} receipt={rc} nominal={nominal.length} see={() => go("extreme")} />
            )}
            {current === "groups" && <GroupsTable result={result} />}
            {current === "prices" && <Prices projectId={projectId} result={result} currency={currency} />}
            {current === "map" && <RatioMap projectId={projectId} result={result} currency={currency} />}
            {current === "regions" && (
              <Regions
                result={result}
                setup={u}
                currency={currency}
                choose={(region) => change.mutate({ region }, { onSuccess: runIt })}
                busy={change.isPending || act.isPending}
              />
            )}
            {current === "similar" && <Similar result={result} />}
            {current === "extreme" && <Extreme projectId={projectId} result={result} currency={currency} />}
          </StepBody>
          <StepFoot
            back={back}
            note={v.stale ? r.run.stale : null}
            next={
              current !== "extreme"
                ? onward
                : v.accepted
                  ? { label: r.toValues, onPress: toValues }
                  : {
                      label: r.looksRight,
                      disabled: v.stale || act.isPending,
                      onPress: () => act.mutate("accept", { onSuccess: toValues }),
                    }
            }
          />
        </>
      )}
    </StepFrame>
  );
}

type CardProps = { v: RatioSetup; set: (body: RatioPatch) => void };

function SalesCard({ v, set }: CardProps) {
  // Typed until the box loses focus; the card is remounted (keyed on the window) when the window changes.
  const [start, setStart] = useState(v.start);
  const [end, setEnd] = useState(v.end);
  const commit = (key: "start" | "end", value: string) => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(value) && value !== v[key]) set({ [key]: value });
  };
  return (
    <div className="rv-cards">
      <section className="cs-step">
        <h3 className="wiz-group">{r.sales.window}</h3>
        <div className="cs-row">
          <Field
            label={r.sales.from}
            type="date"
            width="short"
            value={start}
            onChange={setStart}
            onBlur={() => commit("start", start)}
          />
          <Field
            label={r.sales.to}
            type="date"
            width="short"
            value={end}
            onChange={setEnd}
            onBlur={() => commit("end", end)}
          />
        </div>
        {v.window_proposed ? (
          <p className="wiz-from">{r.sales.proposed(v.proposed_start)}</p>
        ) : (
          <Button className="wiz-link" onPress={() => set({ reset_window: true })}>
            {r.sales.reset}
          </Button>
        )}
        {v.year_before === 0 && v.last_sale && <div className="bi-warn">{r.sales.none(v.last_sale)}</div>}
      </section>
      <section className="cs-step">
        <h3 className="wiz-group">{r.sales.price}</h3>
        <RadioGroup
          aria-label={r.sales.price}
          className="rv-choices"
          value={v.price}
          onChange={(price) => set({ price: price as "sold" | "time_adjusted" })}
        >
          <Radio value="sold" className="radio dn-format">
            <span className="radio-dot" aria-hidden="true" />
            <span>{r.sales.sold}</span>
          </Radio>
          <Radio value="time_adjusted" className="radio dn-format" isDisabled={!v.time_adjusted}>
            <span className="radio-dot" aria-hidden="true" />
            <span>
              {r.sales.timeAdjusted}
              {!v.time_adjusted && <span className="wiz-from"> · {r.sales.noTime}</span>}
            </span>
          </Radio>
        </RadioGroup>
      </section>
      <table className="tbl">
        <tbody>
          {v.funnel.map((l) => (
            <tr key={l.text} className={l.sign === "=" ? "rv-total" : undefined}>
              <td className="cs-n">{l.sign === "-" ? "−" : l.sign}</td>
              <td className="cs-n">{num(l.count)}</td>
              <td>{l.text}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="cs-step">
        <h3 className="wiz-group">{r.sales.perGroup}</h3>
        <table className="tbl">
          <thead>
            <tr>
              <th>{r.table.group}</th>
              <th className="cs-n">{r.table.sales}</th>
            </tr>
          </thead>
          <tbody>
            {v.groups.map((g) => (
              <tr key={g.id}>
                <td>
                  <span className="mg-sw ab-sw" style={{ background: g.color }} />
                  {g.name}
                </td>
                <td className="cs-n">{num(g.sales)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

/** A number the user can change: committed when the box loses focus; a new value starts it over. */
function NumberEdit(props: { label: string; short?: string; value: number; onCommit: (v: number) => void }) {
  return <NumberBox key={props.value} {...props} />;
}

function NumberBox({
  label,
  short,
  value,
  onCommit,
}: {
  label: string;
  short?: string | undefined;
  value: number;
  onCommit: (v: number) => void;
}) {
  const [text, setText] = useState(String(value));
  return (
    <span className="rv-num">
      <Field
        label={short ?? label}
        type="number"
        width="short"
        value={text}
        onChange={setText}
        onBlur={() => {
          const n = Number.parseFloat(text);
          if (Number.isFinite(n) && n !== value) onCommit(n);
          else setText(String(value));
        }}
      />
    </span>
  );
}

const CATS = [
  "residential",
  "residential_homogeneous",
  "residential_rural",
  "apartments",
  "commercial",
  "vacant",
  "agricultural",
] as const;
type Cat = (typeof CATS)[number];
const range = (low: number, high: number) => ({ low, high });
const IAAO: RatioTargets = {
  level_low: 0.9,
  level_high: 1.1,
  prb_good: 0.05,
  prb_bad: 0.1,
  vei: 10,
  min_sales: 5,
  residential: range(5, 15),
  residential_homogeneous: range(4, 10),
  residential_rural: range(10, 20),
  apartments: range(7, 20),
  commercial: range(10, 25),
  vacant: range(10, 20),
  agricultural: range(10, 25),
};

function codRange(g: RatioTargets, c: string) {
  return (CATS as readonly string[]).includes(c) ? g[c as Cat] : null;
}

function StandardsCard({ v, set }: CardProps) {
  const g = v.targets;
  const put = (patch: Partial<RatioTargets>) => set({ targets: { ...g, ...patch } });
  const s = r.standards;
  const changed = JSON.stringify(g) !== JSON.stringify(IAAO);
  return (
    <div className="rv-cards">
      <p className="wiz-from">{s.source}</p>
      <table className="tbl rv-targets">
        <thead>
          <tr>
            <th>{s.what}</th>
            <th>{s.target}</th>
            <th>{s.means}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{s.level}</td>
            <td>
              <span className="cs-row rv-pair">
                <NumberEdit
                  label={`${s.from} (${s.level})`}
                  short={s.from}
                  value={g.level_low}
                  onCommit={(n) => put({ level_low: n })}
                />
                <NumberEdit
                  label={`${s.to} (${s.level})`}
                  short={s.to}
                  value={g.level_high}
                  onCommit={(n) => put({ level_high: n })}
                />
              </span>
            </td>
            <td>{s.levelWhy}</td>
          </tr>
          <tr>
            <td>{s.vei}</td>
            <td>
              <NumberEdit label={s.vei} short="± %" value={g.vei} onCommit={(n) => put({ vei: n })} />
            </td>
            <td>{s.veiWhy}</td>
          </tr>
          <tr>
            <td>{s.prb}</td>
            <td>
              <span className="cs-row rv-pair">
                <NumberEdit
                  label={`${s.prbGood} (${s.prb})`}
                  short={s.prbGood}
                  value={g.prb_good}
                  onCommit={(n) => put({ prb_good: n })}
                />
                <NumberEdit
                  label={`${s.prbBad} (${s.prb})`}
                  short={s.prbBad}
                  value={g.prb_bad}
                  onCommit={(n) => put({ prb_bad: n })}
                />
              </span>
            </td>
            <td>{s.prbWhy}</td>
          </tr>
          <tr>
            <td>{s.prd}</td>
            <td className="wiz-from">{s.prdNot}</td>
            <td>{s.prdWhy}</td>
          </tr>
          <tr>
            <td>{s.minSales}</td>
            <td>
              <NumberEdit
                label={s.minSales}
                short={s.sales}
                value={g.min_sales}
                onCommit={(n) => put({ min_sales: Math.max(1, Math.round(n)) })}
              />
            </td>
            <td>{s.minSalesWhy}</td>
          </tr>
        </tbody>
      </table>
      <section className="cs-step">
        <h3 className="wiz-group">{s.cod}</h3>
        <p className="wiz-from">{s.codWhy}</p>
        <table className="tbl">
          <thead>
            <tr>
              <th>{s.category}</th>
              <th>{s.codRange}</th>
            </tr>
          </thead>
          <tbody>
            {CATS.map((c) => (
              <tr key={c}>
                <td>{s.cls[c]}</td>
                <td>
                  <span className="cs-row rv-pair">
                    <NumberEdit
                      label={`${s.from} (${s.cls[c]})`}
                      short={s.from}
                      value={g[c].low}
                      onCommit={(n) => put({ [c]: { ...g[c], low: n } } as Partial<RatioTargets>)}
                    />
                    <NumberEdit
                      label={`${s.to} (${s.cls[c]})`}
                      short={s.to}
                      value={g[c].high}
                      onCommit={(n) => put({ [c]: { ...g[c], high: n } } as Partial<RatioTargets>)}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {changed && (
        <Button className="wiz-link" onPress={() => set({ targets: IAAO })}>
          {s.reset}
        </Button>
      )}
      <Tick isSelected={v.trim} onChange={(on) => set({ trim: on })}>
        {s.trim}
      </Tick>
      <section className="cs-step">
        <h3 className="wiz-group">{s.classes}</h3>
        <p className="wiz-from">{s.classesWhy}</p>
        <table className="tbl">
          <thead>
            <tr>
              <th>{r.table.group}</th>
              <th>{s.category}</th>
              <th className="cs-n">{s.codRange}</th>
            </tr>
          </thead>
          <tbody>
            {v.groups.map((x) => {
              const cr = codRange(g, x.cls);
              return (
                <tr key={x.id}>
                  <td>
                    <span className="mg-sw ab-sw" style={{ background: x.color }} />
                    {x.name}
                  </td>
                  <td>
                    <Choice
                      label={`${s.category}: ${x.name}`}
                      hideLabel
                      value={x.cls}
                      options={[...CATS, "none" as const].map((c) => [c, s.cls[c] ?? c] as [string, string])}
                      onChange={(c) => set({ classes: { [x.id]: c as Class } })}
                    />{" "}
                    {x.proposed && <span className="wiz-from">{s.proposed}</span>}
                  </td>
                  <td className="cs-n">{cr ? `${cr.low} to ${cr.high}` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

/** The VEI's badge: met unless significantly outside (the exposure draft's Appendix E). */
function veiOk(g: { vei_verdict?: string | null; verdict?: { judged: boolean } | null }): boolean | null {
  if (g.vei_verdict === "compliant" || g.vei_verdict === "not_significant") return true;
  if (g.vei_verdict === "regressive" || g.vei_verdict === "progressive")
    return g.verdict?.judged ? false : null;
  return null;
}

function judged(g: RatioStudy) {
  return !!g.verdict?.judged;
}

/** The first page a board member can read: one paragraph, then a card per model group. */
function Summary({
  result,
  receipt,
  nominal,
  see,
}: {
  result: FieldResult;
  receipt: NonNullable<RatioView["receipt"]>;
  nominal: number;
  see: () => void;
}) {
  const o = result.overall;
  const js = result.groups.filter(judged);
  const levelOk = js.filter((g) => g.verdict?.level);
  const lo = "90%";
  const hi = "110%";
  let text = o.median ? r.summary.head(result.name, pct(o.median), receipt.start, receipt.end) : "";
  if (js.length)
    text +=
      levelOk.length === 0
        ? r.summary.levelAll(lo, hi)
        : levelOk.length === js.length
          ? r.summary.levelNone(lo, hi)
          : r.summary.levelSome(levelOk.length, js.length, lo, hi);
  const loose = js.filter((g) => g.verdict?.cod === false).map((g) => `${g.name} (COD ${num(g.cod, 1)})`);
  if (js.length) text += loose.length ? r.summary.notUniform(loose.join(", ")) : r.summary.uniform;
  const tight = js.filter((g) => g.verdict?.cod_low).map((g) => `${g.name} (COD ${num(g.cod, 1)})`);
  if (tight.length) text += r.summary.suspect(tight.join(", "));
  const tilted = js
    .filter((g) => g.vei_verdict === "regressive" || g.vei_verdict === "progressive")
    .map((g) => `${g.name} (${r.table.verdicts[g.vei_verdict ?? ""]})`);
  if (js.length) text += tilted.length ? r.summary.vertical(tilted.join(", ")) : r.summary.noVertical;
  const names = result.trimmed
    .filter((x) => x.nominal)
    .map((x) => x.address ?? x.key_sale)
    .slice(0, 4)
    .join(", ");
  return (
    <div className="rv-cards">
      <p className="rv-head">{text}</p>
      <Scorecard groups={result.groups} />
      {nominal > 0 && (
        <div className="bi-warn">
          {r.summary.nominal(nominal, names)}{" "}
          <Button className="wiz-link" onPress={see}>
            {r.summary.see}
          </Button>
        </div>
      )}
      <p className="wiz-from">
        {r.summary.ran(
          when(receipt.ran_at),
          o.sales,
          receipt.start,
          receipt.end,
          receipt.price === "sold" ? r.summary.asSold : r.summary.adjusted,
        )}
      </p>
    </div>
  );
}

/** One line per model group, its three questions in columns: a mark, the figure, a word, aligned down the table so
 * groups compare at a glance. */
function Scorecard({ groups }: { groups: RatioStudy[] }) {
  const c = r.card;
  return (
    <table className="tbl rv-score">
      <thead>
        <tr>
          <th>{r.table.group}</th>
          <th className="cs-n">{r.table.sales}</th>
          <th>
            <InfoTip label={c.level} text={c.levelWhy} />
          </th>
          <th>
            <InfoTip label={c.uniform} text={c.uniformWhy} />
          </th>
          <th>
            <InfoTip label={c.vertical} text={c.verticalWhy} />
          </th>
        </tr>
      </thead>
      <tbody>
        {groups.map((g) => {
          const v = g.verdict;
          const name = (
            <td>
              <span className="mg-sw ab-sw" style={{ background: g.color }} />
              {g.name}
            </td>
          );
          if (!g.sales || g.median == null)
            return (
              <tr key={g.id}>
                {name}
                <td className="cs-n">0</td>
                <td colSpan={3} className="wiz-from">
                  {c.noSales}
                </td>
              </tr>
            );
          if (!v?.judged)
            return (
              <tr key={g.id}>
                {name}
                <td className="cs-n">{num(g.sales)}</td>
                <td>
                  <Score v={null} figure={ratioText(g.median)} />
                </td>
                <td colSpan={2} className="wiz-from">
                  {c.tooFew}
                </td>
              </tr>
            );
          // The VEI decides; with too few sales for it, the PRB.
          const byVei = g.vei_verdict && g.vei_verdict !== "insufficient";
          const tilted = byVei
            ? g.vei_verdict === "regressive" || g.vei_verdict === "progressive"
            : v.prb === false;
          const lower = byVei ? g.vei_verdict === "regressive" : (g.prb ?? 0) < 0;
          return (
            <tr key={g.id}>
              {name}
              <td className="cs-n">{num(g.sales)}</td>
              <td>
                <Score
                  v={verdictOf(v.level)}
                  figure={ratioText(g.median)}
                  word={v.level ? c.inRange : g.median < 1 ? c.low : c.high}
                />
              </td>
              <td>
                <Score
                  v={verdictOf(v.cod_low ? false : v.cod)}
                  figure={num(g.cod, 1)}
                  word={v.cod_low ? c.tooEven : v.cod === false ? c.varied : c.even}
                />
              </td>
              <td>
                <Score
                  v={byVei ? verdictOf(veiOk(g)) : prbVerdict(g)}
                  figure={
                    byVei && g.vei != null
                      ? `${signed(g.vei, 1)}%`
                      : `${g.prb == null ? "—" : signed(g.prb, 3)}`
                  }
                  word={
                    tilted
                      ? lower
                        ? c.dearerLower
                        : c.dearerHigher
                      : g.vei_verdict === "not_significant"
                        ? c.notSignificant
                        : c.alike
                  }
                  note={byVei ? "VEI" : "PRB"}
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** A verdict cell: pill, figure and word in the same three columns on every row. */
export function Score({
  v,
  figure,
  word,
  note,
}: {
  v: Verdict | null;
  figure: string;
  word?: string;
  note?: string;
}) {
  return (
    <span className="rv-score-cell">
      <span className="rv-score-pill">
        <Pill v={v} />
      </span>
      <span className="rv-fig">
        {figure}
        {note && <span className="wiz-from"> {note}</span>}
      </span>
      <span>{word ?? r.card.notJudged}</span>
    </span>
  );
}

/** A figure with its pill: the pill at the cell's left edge, the figure at its right, so a pill never moves the
 * figure; every sale's figure under it. */
function cell(
  v: Verdict | null | undefined,
  text: string,
  every?: string | null,
  low?: boolean | null,
  label?: string,
) {
  return (
    <>
      <span className="rv-cell">
        <span className="rv-cell-pill">
          <Pill v={v} {...(label ? { label } : {})} />
          {low && <span className="pill pill-bad">{r.table.low}</span>}
        </span>
        <span>{text}</span>
      </span>
      {every != null && <span className="rv-every">{r.table.every(every)}</span>}
    </>
  );
}

function GroupsTable({ result }: { result: FieldResult }) {
  const tb = r.table;
  const row = (g: RatioStudy, total = false) => {
    const v = g.verdict;
    const e = g.every;
    if (!g.sales && !g.trimmed)
      return (
        <tr key={g.id || "all"}>
          <td>
            <span className="mg-sw ab-sw" style={{ background: g.color }} />
            {g.name}
          </td>
          <td className="cs-n">0</td>
          <td colSpan={8} className="wiz-from">
            {tb.noSales}
          </td>
        </tr>
      );
    const pm = (x: number | null | undefined, d: number) => (x == null ? "—" : signed(x, d));
    return (
      <tr key={g.id || "all"} className={total ? "rv-total" : undefined}>
        <td>
          {!total && <span className="mg-sw ab-sw" style={{ background: g.color }} />}
          {g.name}
        </td>
        <td className="cs-n">{cell(null, num(g.sales), e ? num(e.sales) : null)}</td>
        <td className="cs-n">{num(g.trimmed)}</td>
        <td className="cs-n">
          {cell(verdictOf(v?.level), ratioText(g.median), e ? ratioText(e.median) : null)}
        </td>
        <td className="cs-n wiz-from">
          {g.low != null && g.high != null ? `${ratioText(g.low)} to ${ratioText(g.high)}` : "—"}
        </td>
        <td className="cs-n">
          {cell(verdictOf(v?.cod), num(g.cod, 1), e ? num(e.cod, 1) : null, v?.cod_low)}
        </td>
        <td className="cs-n">
          {g.vei_verdict
            ? cell(
                verdictOf(veiOk(g)),
                g.vei != null ? `${signed(g.vei, 1)}%` : "—",
                e?.vei != null ? `${signed(e.vei, 1)}%` : null,
                null,
                tb.verdicts[g.vei_verdict] ?? g.vei_verdict,
              )
            : "—"}
        </td>
        <td className="cs-n">{cell(prbVerdict(g), pm(g.prb, 3), e ? pm(e.prb, 3) : null)}</td>
        <td className="cs-n">{cell(null, num(g.prd, 3), e ? num(e.prd, 3) : null)}</td>
        <td className="cs-n">{cell(null, num(g.mki, 3), e ? num(e.mki, 3) : null)}</td>
      </tr>
    );
  };
  return (
    <>
      <table className="tbl">
        <thead>
          <tr>
            <th>{tb.group}</th>
            <th className="cs-n">{tb.sales}</th>
            <th className="cs-n">
              <InfoTip label={tb.trimmed} text={tb.trimmedWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.median} text={tb.medianWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.range} text={tb.rangeWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.cod} text={tb.codWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.vei} text={tb.veiWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.prb} text={tb.prbWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.prd} text={tb.prdWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.mki} text={tb.mkiWhy} />
            </th>
          </tr>
        </thead>
        <tbody>{result.groups.map((g) => row(g))}</tbody>
        <tfoot>{row(result.overall, true)}</tfoot>
      </table>
      <p className="wiz-from">{tb.note}</p>
    </>
  );
}

function Prices({
  projectId,
  result,
  currency,
}: {
  projectId: string;
  result: FieldResult;
  currency: string;
}) {
  const studied = result.groups.filter((g) => g.sales > 0);
  const [gid, setGid] = useState(studied.slice().sort((a, b) => b.sales - a.sales)[0]?.id ?? "");
  const g = result.groups.find((x) => x.id === gid) ?? result.overall;
  const pts = useQuery({
    queryKey: ["ratio-points", projectId, result.field, gid],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/points", {
          params: { path: { project_id: projectId }, query: { field: result.field, group: gid } },
        }),
      ),
  });
  const p = r.prices;
  return (
    <div className="rv-cards">
      <h2 className="wiz-q">{p.title(g.name)}</h2>
      <div className="cs-row">
        <Choice
          label={r.table.group}
          hideLabel
          value={gid}
          options={[
            ...studied.map((x) => [x.id, x.name] as [string, string]),
            ["", result.overall.name] as [string, string],
          ]}
          onChange={setGid}
        />
        <span className="wiz-from">{p.lede}</span>
      </div>
      <Scatter
        points={(pts.data ?? []) as [number, number, boolean][]}
        fifths={g.fifths}
        currency={currency}
      />
      <p className="wiz-from">{p.trimmedDot}</p>
      {g.fifths.length > 0 && (
        <table className="tbl">
          <thead>
            <tr>
              <th>{p.fifth}</th>
              <th className="cs-n">{r.table.sales}</th>
              <th className="cs-n">{r.table.median}</th>
            </tr>
          </thead>
          <tbody>
            {g.fifths.map((f) => (
              <tr key={f.low}>
                <td>
                  {money(f.low, currency)} to {money(f.high, currency)}
                </td>
                <td className="cs-n">{num(f.sales)}</td>
                <td className="cs-n">{ratioText(f.median)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="wiz-from">{p.flat}</p>
      <section className="cs-step">
        <h3 className="wiz-group">{p.strata}</h3>
        {g.strata.length ? (
          <>
            <p>
              {p.vei(
                g.vei == null ? "—" : `${signed(g.vei, 1)}%`,
                g.vei_significance == null ? "—" : `${signed(g.vei_significance, 1)}%`,
                r.table.verdicts[g.vei_verdict ?? ""] ?? "—",
              )}
            </p>
            <BandChart series={[{ label: p.bySale, color: "#d4566f", bands: g.strata }]} />
            <table className="tbl">
              <thead>
                <tr>
                  <th>{p.stratum}</th>
                  <th className="cs-n">{r.table.sales}</th>
                  <th className="cs-n">{r.table.median}</th>
                  <th className="cs-n">{r.table.range}</th>
                </tr>
              </thead>
              <tbody>
                {g.strata.map((x, k) => (
                  <tr key={`${x.n}-${x.median}-${x.low}-${x.high}`}>
                    <td>{k + 1}</td>
                    <td className="cs-n">{num(x.n)}</td>
                    <td className="cs-n">{ratioText(x.median)}</td>
                    <td className="cs-n">
                      {ratioText(x.low)} to {ratioText(x.high)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="wiz-from">{p.noVei}</p>
        )}
      </section>
    </div>
  );
}

type Band = { median?: number | null; low?: number | null; high?: number | null };

/** Groups of sales from the cheapest to the dearest, each its median ratio with its 90% range as a bar (the VEI's
 * chart, as openratiostudy.com draws it); several series side by side in each group, the standard's level in green. */
function BandChart({ series }: { series: { label: string; color: string; bands: Band[] }[] }) {
  const [ref, W] = useWidth<SVGSVGElement>();
  const H = 260;
  const L = 52;
  const R = 16;
  const T = 12;
  const B = 34;
  const n = Math.max(...series.map((x) => x.bands.length), 1);
  const vals = series
    .flatMap((x) => x.bands.flatMap((b) => [b.low, b.high, b.median]))
    .filter((v) => v != null);
  const rlo = Math.min(0.85, ...(vals as number[])) - 0.05;
  const rhi = Math.max(1.15, ...(vals as number[])) + 0.05;
  const slot = (W - L - R) / n;
  const y = (v: number) => T + (H - T - B) * (1 - (v - rlo) / (rhi - rlo));
  const off = (k: number) =>
    series.length === 1 ? 0 : (k - (series.length - 1) / 2) * Math.min(18, slot / 4);
  const rticks: number[] = [];
  for (let v = Math.ceil(rlo * 10) / 10; v <= rhi; v += 0.1) rticks.push(Math.round(v * 10) / 10);
  const name = (k: number) => (k === 0 ? r.regions.lowest : k === n - 1 ? r.regions.highest : String(k + 1));
  return (
    <figure className="rv-figure">
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${H}`}
        height={H}
        className="rv-chart"
        role="img"
        aria-label={series.map((x) => x.label).join("; ")}
      >
        <rect x={L} y={y(1.1)} width={W - L - R} height={y(0.9) - y(1.1)} fill="#e7f5ec" />
        {rticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#e2e4e6" />
            <text x={L - 6} y={y(v) + 4} fontSize="11" textAnchor="end" fill="#555">
              {v.toFixed(1)}
            </text>
          </g>
        ))}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="#888" />
        {Array.from({ length: n }, (_, k) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
          <text key={k} x={L + slot * (k + 0.5)} y={H - B + 16} fontSize="11" textAnchor="middle" fill="#555">
            {name(k)}
          </text>
        ))}
        {series.map((sr, j) =>
          sr.bands.map((b, k) => {
            const cx = L + slot * (k + 0.5) + off(j);
            return b.median == null ? null : (
              // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
              <g key={`${sr.label}-${k}`}>
                {b.low != null && b.high != null && (
                  <line x1={cx} x2={cx} y1={y(b.low)} y2={y(b.high)} stroke={sr.color} strokeWidth="2" />
                )}
                <circle cx={cx} cy={y(b.median)} r="4.5" fill={sr.color} />
              </g>
            );
          }),
        )}
      </svg>
      {series.length > 1 && (
        <figcaption className="rv-legend">
          {series.map((sr) => (
            <span key={sr.label}>
              <span className="rv-swatch" style={{ background: sr.color, borderColor: sr.color }} />
              {sr.label}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

function Scatter({
  points,
  fifths,
  currency,
}: {
  points: [number, number, boolean][];
  fifths: RatioStudy["fifths"];
  currency: string;
}) {
  const [ref, W] = useWidth<SVGSVGElement>();
  const H = 280;
  const L = 52;
  const R = 16;
  const T = 12;
  const B = 30;
  const kept = points.filter((x) => !x[2]);
  const prices = (kept.length ? kept : points).map((x) => x[0]).filter((x) => x > 0);
  if (!prices.length) return <svg ref={ref} className="rv-chart" height={H} />;
  const lo = Math.log10(Math.min(...prices));
  const hi = Math.log10(Math.max(...prices)) + 0.01;
  const rs = kept.map((x) => x[1]).sort((a, b) => a - b);
  const rlo = Math.min(0.5, rs[Math.floor(rs.length * 0.01)] ?? 0.5) - 0.05;
  const rhi = Math.max(1.2, rs[Math.floor(rs.length * 0.99)] ?? 1.2) + 0.05;
  const x = (v: number) => L + ((W - L - R) * (Math.log10(Math.max(v, 10 ** lo)) - lo)) / (hi - lo);
  const y = (v: number) => T + (H - T - B) * (1 - (Math.min(Math.max(v, rlo), rhi) - rlo) / (rhi - rlo));
  const ticks: number[] = [];
  for (let e = Math.floor(lo); e <= Math.ceil(hi); e++)
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** e;
      if (Math.log10(v) >= lo && Math.log10(v) <= hi) ticks.push(v);
    }
  const rticks: number[] = [];
  for (let v = Math.ceil(rlo * 5) / 5; v <= rhi; v += 0.2) rticks.push(Math.round(v * 10) / 10);
  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      height={H}
      className="rv-chart"
      role="img"
      aria-label={r.prices.lede}
    >
      <rect x={L} y={y(1.1)} width={W - L - R} height={y(0.9) - y(1.1)} fill="#e7f5ec" />
      {rticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#e2e4e6" />
          <text x={L - 6} y={y(v) + 4} fontSize="11" textAnchor="end" fill="#555">
            {v.toFixed(1)}
          </text>
        </g>
      ))}
      <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="#888" />
      {ticks.map((v) => (
        <text key={v} x={x(v)} y={H - B + 16} fontSize="11" textAnchor="middle" fill="#555">
          {new Intl.NumberFormat(undefined, { style: "currency", currency, notation: "compact" }).format(v)}
        </text>
      ))}
      {points.map(([p, q, trimmed], k) => (
        <circle
          // biome-ignore lint/suspicious/noArrayIndexKey: points have no key of their own
          key={k}
          cx={x(p)}
          cy={y(q)}
          r="2.6"
          fill={trimmed ? "#9a9a9a" : "#d4566f"}
          opacity="0.55"
        />
      ))}
      {fifths.map((f) => (
        <line
          key={f.low}
          x1={x(f.low)}
          x2={x(f.high)}
          y1={y(f.median)}
          y2={y(f.median)}
          stroke="#222"
          strokeWidth="2.5"
        />
      ))}
    </svg>
  );
}

function Similar({ result }: { result: FieldResult }) {
  const sm = r.similar;
  const reads = (c: number | null | undefined) =>
    c == null ? "—" : c < 20 ? sm.tight : c < 40 ? sm.some : sm.wide;
  return (
    <>
      <p className="wiz-lede">{sm.lede}</p>
      <table className="tbl">
        <thead>
          <tr>
            <th>{r.table.group}</th>
            <th className="cs-n">{sm.parcels}</th>
            <th className="cs-n">{sm.clusters}</th>
            <th className="cs-n">
              <InfoTip label={sm.chd} text={sm.chdWhy} />
            </th>
            <th>{sm.reads}</th>
          </tr>
        </thead>
        <tbody>
          {result.groups.map((g) => (
            <tr key={g.id}>
              <td>
                <span className="mg-sw ab-sw" style={{ background: g.color }} />
                {g.name}
              </td>
              <td className="cs-n">{num(g.parcels)}</td>
              <td className="cs-n">{num(g.clusters)}</td>
              <td className="cs-n">{num(g.median_chd, 1)}</td>
              <td>{reads(g.median_chd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Extreme({
  projectId,
  result,
  currency,
}: {
  projectId: string;
  result: FieldResult;
  currency: string;
}) {
  const queryClient = useQueryClient();
  const [done, setDone] = useState<Set<string>>(new Set());
  const exclude = useMutation({
    mutationFn: async (m: { key: string; note: string }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/clean/marks/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: m.key } },
          body: { action: "exclude", note: m.note },
        }),
      ),
    onSuccess: (_, m) => {
      setDone((d) => new Set(d).add(m.key));
      // Check sales is now out of date; this step's results are left on screen, so several can be marked.
      void queryClient.invalidateQueries({ queryKey: stepKey("clean", projectId) });
      void queryClient.invalidateQueries({ queryKey: ["clean-review", projectId] });
    },
  });
  const e = r.extreme;
  if (!result.trimmed.length) return <p className="wiz-from">{e.none}</p>;
  return (
    <>
      <p className="wiz-lede">{e.lede}</p>
      <table className="tbl">
        <thead>
          <tr>
            <th>{e.address}</th>
            <th>{e.group}</th>
            <th>{e.sold}</th>
            <th className="cs-n">{e.price}</th>
            <th className="cs-n">{e.value}</th>
            <th className="cs-n">{e.ratio}</th>
            <th>{e.likely}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {result.trimmed.map((x) => (
            <tr key={x.key_sale}>
              <td>{x.address ?? x.key_sale}</td>
              <td>{x.group_name}</td>
              <td>{day(x.sale_date)}</td>
              <td className="cs-n">{money(x.price, currency)}</td>
              <td className="cs-n">{money(x.value, currency)}</td>
              <td className="cs-n">{num(x.ratio, x.ratio >= 100 ? 0 : 2)}</td>
              <td>{x.nominal ? e.nominal : x.ratio > 1 ? e.high : e.low}</td>
              <td>
                {done.has(x.key_sale) ? (
                  <span className="wiz-ok">{e.excluded}</span>
                ) : (
                  <Button
                    className="wiz-link"
                    isDisabled={exclude.isPending}
                    onPress={() =>
                      exclude.mutate({
                        key: x.key_sale,
                        note: x.nominal ? e.note(money(x.price, currency)) : "",
                      })
                    }
                  >
                    {e.exclude}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {exclude.error && (
        <p className="error" role="alert">
          {exclude.error.message}
        </p>
      )}
    </>
  );
}

/** openratiostudy.com's colours: blue below 1 (deepest at 0.5), white at 1, red above (deepest at 2). */
function ratioColor(q: number): string {
  if (!Number.isFinite(q)) return "#94a3b8";
  if (q <= 1) {
    const c = Math.round(255 * Math.max(0, Math.min(1, (q - 0.5) / 0.5)));
    return `rgb(${c}, ${c}, 255)`;
  }
  const c = Math.round(255 * (1 - Math.max(0, Math.min(1, q - 1))));
  return `rgb(255, ${c}, ${c})`;
}

function ratioStroke(q: number): string {
  return q < 0.9 ? "#1d4ed8" : q > 1.1 ? "#b91c1c" : "#475569";
}

/** Each sale on the map, coloured by its ratio: clusters of high or low ratios show where values are off. */
function RatioMap({
  projectId,
  result,
  currency,
}: {
  projectId: string;
  result: FieldResult;
  currency: string;
}) {
  const studied = result.groups.filter((g) => g.sales > 0);
  const [gid, setGid] = useState("");
  const pts = useQuery({
    queryKey: ["ratio-map", projectId, result.field, gid],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/map", {
          params: { path: { project_id: projectId }, query: { field: result.field, group: gid } },
        }),
      ),
  });
  const el = useRef<HTMLElement>(null);
  useEffect(() => {
    const data = pts.data;
    if (!el.current || !data || data.length === 0) return;
    const m = L.map(el.current, { preferCanvas: true, zoomSnap: 0.25 });
    addBasemap(m);
    const renderer = L.canvas({ padding: 0.3 });
    const fmt = (v: number) => money(v, currency);
    for (const p of data) {
      L.circleMarker([p.lat, p.lon], {
        renderer,
        radius: p.trimmed ? 3 : 4.5,
        color: p.trimmed ? "#9a9a9a" : ratioStroke(p.ratio),
        weight: 0.85,
        fillColor: p.trimmed ? "#d0d0d0" : ratioColor(p.ratio),
        fillOpacity: 0.85,
      })
        .bindTooltip(
          `${r.map.ratio} ${num(p.ratio, 3)} · ${r.map.price} ${fmt(p.price)} · ${r.map.value} ${fmt(p.value)}${p.trimmed ? ` · ${r.map.trimmed}` : ""}`,
        )
        .addTo(m);
    }
    const b = L.latLngBounds(data.map((p) => [p.lat, p.lon] as [number, number]));
    if (b.isValid()) m.fitBounds(b, { padding: [12, 12] });
    return () => {
      m.remove();
    };
  }, [pts.data, currency]);
  const mp = r.map;
  return (
    <div className="rv-cards">
      <div className="cs-row">
        <Choice
          label={r.table.group}
          hideLabel
          value={gid}
          options={[
            ["", result.overall.name] as [string, string],
            ...studied.map((x) => [x.id, x.name] as [string, string]),
          ]}
          onChange={setGid}
        />
        <span className="wiz-from">{mp.lede}</span>
      </div>
      {pts.data && pts.data.length === 0 ? (
        <p className="wiz-from">{mp.none}</p>
      ) : (
        <section ref={el} className="rv-map" aria-label={mp.label} />
      )}
      <div className="rv-legend">
        {mp.legend.map(([q, label]) => (
          <span key={label}>
            <span className="rv-swatch" style={{ background: ratioColor(q), borderColor: ratioStroke(q) }} />
            {label}
          </span>
        ))}
        <span>
          <span className="rv-swatch" style={{ background: "#d0d0d0", borderColor: "#9a9a9a" }} />
          {mp.trimmed}
        </span>
      </div>
    </div>
  );
}

/** The median ratio by the price level of the region each sale is in (openratiostudy.com's neighbourhood price
 * levels): it tells real vertical inequity from invalid sales at low prices in dear areas. */
function Regions({
  result,
  setup,
  currency,
  choose,
  busy,
}: {
  result: FieldResult;
  setup: RatioSetup | undefined;
  currency: string;
  choose: (region: string) => void;
  busy: boolean;
}) {
  const studied = result.groups.filter((g) => g.sales > 0);
  const [gid, setGid] = useState("");
  const g = result.groups.find((x) => x.id === gid) ?? result.overall;
  const rg = g.regions;
  const rr = r.regions;
  return (
    <div className="rv-cards">
      <p className="wiz-lede">{rr.lede}</p>
      <div className="cs-row">
        {setup && (
          <Choice
            label={rr.field}
            value={setup.region}
            isDisabled={busy}
            options={[
              ["", rr.noField] as [string, string],
              ...setup.regions.map((x) => [x.value, x.label] as [string, string]),
            ]}
            onChange={choose}
          />
        )}
        <Choice
          label={r.table.group}
          value={gid}
          options={[
            ["", result.overall.name] as [string, string],
            ...studied.map((x) => [x.id, x.name] as [string, string]),
          ]}
          onChange={setGid}
        />
      </div>
      {!rg ? (
        <p className="wiz-from">
          {setup?.region ? rr.notRun : setup && setup.regions.length === 0 ? rr.noLocations : rr.choose}
        </p>
      ) : rg.strata.length < 2 ? (
        <p className="wiz-from">{rr.few(rg.sales, rg.regions)}</p>
      ) : (
        <>
          <p>
            {rr.reading(
              rg.regions,
              rg.sales,
              rg.vei == null ? "—" : `${signed(rg.vei, 1)}%`,
              r.table.verdicts[rg.vei_verdict] ?? rg.vei_verdict,
            )}
          </p>
          <BandChart
            series={[
              { label: rr.byLevel, color: "#2f5d9b", bands: rg.strata },
              ...(g.strata.length ? [{ label: rr.bySale, color: "#d4566f", bands: g.strata }] : []),
            ]}
          />
          <table className="tbl">
            <thead>
              <tr>
                <th>{rr.group}</th>
                <th className="cs-n">{rr.regionsCol}</th>
                <th className="cs-n">{r.table.sales}</th>
                <th className="cs-n">{rr.level}</th>
                <th className="cs-n">{r.table.median}</th>
                <th className="cs-n">{r.table.range}</th>
              </tr>
            </thead>
            <tbody>
              {rg.strata.map((x, k) => (
                <tr key={`${x.level}-${x.n}-${x.median}`}>
                  <td>{k === 0 ? rr.lowest : k === rg.strata.length - 1 ? rr.highest : k + 1}</td>
                  <td className="cs-n">{num(x.regions)}</td>
                  <td className="cs-n">{num(x.n)}</td>
                  <td className="cs-n">{money(x.level, currency)}</td>
                  <td className="cs-n">{ratioText(x.median)}</td>
                  <td className="cs-n">
                    {ratioText(x.low)} to {ratioText(x.high)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="wiz-from">{rr.compare(g.vei == null ? "—" : `${signed(g.vei, 1)}%`)}</p>
        </>
      )}
    </div>
  );
}
