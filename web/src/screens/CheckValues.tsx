import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Radio } from "react-aria-components";
import { useMarkSale } from "../api/clean";
import {
  api,
  type FieldResult,
  type RatioPatch,
  type RatioSetup,
  type RatioView,
  unwrap,
} from "../api/client";
import { useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { DateField } from "../components/DateField";
import { Disclose } from "../components/Disclose";
import { ExcludedSince } from "../components/ExcludedSince";
import { Choice, Radios } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { OnTheMap } from "../components/OnTheMap";
import { Seg } from "../components/Seg";
import { ShowOnMapButton } from "../components/ShowOnMap";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame, type StepStatus } from "../components/Steps";
import { InfoTip } from "../components/Tip";
import { Val } from "../components/Val";
import { LoadingBar } from "../components/Waiting";
import { BY_SALE } from "../lib/colours";
import { day, money, num, ratioText, signed, when } from "../lib/format";
import { setStepPick, useMapStep } from "../lib/mapstep";
import { onward as goOnTo } from "../lib/returnto";
import { t } from "../wording";
import { ExtremeMap } from "./ExtremeMap";
import { SavedGroupsOnMap } from "./GroupMap";
import { SimilarMap } from "./SimilarMap";
import { AssignTable, StandardsTable, WhoseCard } from "./Standards";
import { BandChart, Scatter } from "./ValueCharts";
import { RatioMap, Regions } from "./ValueMap";
import { GroupsTable, judged, Scorecard } from "./ValueTables";

const r = t.ratio;
type RStep =
  | "what"
  | "sales"
  | "whose"
  | "standards"
  | "assign"
  | "run"
  | "summary"
  | "prices"
  | "map"
  | "regions"
  | "similar"
  | "extreme";
const STEPS: RStep[] = [
  "what",
  "sales",
  "whose",
  "standards",
  "assign",
  "run",
  "summary",
  "prices",
  "map",
  "regions",
  "similar",
  "extreme",
];
const AFTER: RStep[] = ["summary", "prices", "map", "regions", "similar", "extreme"];

const pct = (v: number) => Math.round(100 * v);

/** Step 4, Check my values (SPEC F8): the values on the roll against what parcels sold for, judged against the
 * IAAO's targets (or the user's), one task at a time. */
export function CheckValuesTab({ projectId, currency }: { projectId: string; currency: string }) {
  const state = useStep("ratio", projectId);
  const v = state.data;
  const { setup, change } = useStepSetup("ratio", projectId, !!v && v.blocked.length === 0);
  const act = useStepAct("ratio", projectId);
  const nav = useStepNav<RStep>();
  // Several sets of values checked: the results show one at a time, the same one from part to part.
  const [shown, setShown] = useState<string | null>(null);
  // The model group the map shows ("" every group): picked by a row's Show on map or on the map itself.
  const mapGroup = useMapStep()?.pick ?? "";
  if (!v) return <LoadingBar error={state.error} />;
  const running = v.status === "running";
  const rc = v.receipt;
  const fresh = !!rc && !v.stale;
  const fallback: RStep = running ? "run" : fresh ? "summary" : rc ? "run" : "what";
  // A step remembered that's no longer one (By model group, folded into Summary): the tab's own pick.
  const asked = nav.current(v.status, fallback, "summary");
  const current = STEPS.includes(asked) ? asked : fallback;
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
  const result: FieldResult | undefined = rc?.results.find((x) => x.field === shown) ?? rc?.results[0];
  const nominal = result?.trimmed.filter((x) => x.nominal) ?? [];
  const called = rc ? (v.stale ? "attention" : "done") : "blank";
  const statusOf = (key: RStep): StepStatus => {
    // The results' pages: only Extreme values is ever marked (the nominal values it found, or Looks right).
    if (AFTER.includes(key)) {
      if (!rc || key !== "extreme") return "blank";
      if (nominal.length) return "attention";
      return v.accepted ? "done" : "blank";
    }
    if (key === "run") return called;
    if (key === "what" && v.skipped) return "done";
    if (!setup.data) return "blank";
    return key === "sales" && setup.data.year_before === 0 ? "attention" : "done";
  };
  const steps: Step[] = STEPS.map((key) => ({
    key,
    title: r.steps[key],
    status: statusOf(key),
    disabled: (AFTER.includes(key) && !rc) || (v.skipped && key !== "what"),
  }));
  const i = STEPS.indexOf(current);
  const prev = STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  // On to the next tab, Variables (never past it): back instead to a tab that sent you here (lib/returnto).
  const toValues = () => goOnTo(projectId, "variables");
  const onward = { label: t.step.next, onPress: () => go(STEPS[i + 1] ?? current) };
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
      <StepFrame steps={steps} current="sales" go={() => {}} landing="check">
        <StepBody title={r.sales.title}>
          <div className="bi-warn">
            <b>{r.blocked}</b> {v.blocked[0]}
          </div>
        </StepBody>
      </StepFrame>
    );
  const loading = <LoadingBar />;

  const which = rc && rc.results.length > 1 && result && (
    <Seg
      label={r.what.shown}
      value={result.field}
      options={rc.results.map((x) => [x.field, x.name] as const)}
      onChange={setShown}
    />
  );

  return (
    <StepFrame steps={steps} current={current} go={go} landing="check">
      {current === "what" && (
        <>
          <StepBody title={r.what.title} lede={r.what.lede}>
            {u ? <WhatCard v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot
            next={
              v.skipped
                ? { label: r.what.toValues, onPress: toValues }
                : {
                    label: t.step.next,
                    onPress: () =>
                      u?.check === null
                        ? change.mutate({ check: true }, { onSuccess: () => go("sales") })
                        : go("sales"),
                  }
            }
          />
        </>
      )}
      {current === "sales" && (
        <>
          <StepBody title={r.sales.title} lede={r.sales.lede}>
            {u ? <SalesCard key={`${u.start}|${u.end}`} v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot next={onward} />
        </>
      )}
      {current === "whose" && (
        <>
          <StepBody title={r.standards.whose} lede={r.standards.whoseLede}>
            {u ? <WhoseCard v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "standards" && (
        <>
          <StepBody title={r.standards.title} lede={r.standards.lede}>
            {u ? <StandardsTable v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "assign" && (
        <>
          <StepBody title={r.standards.assignTitle} lede={r.standards.assignLede}>
            <SavedGroupsOnMap projectId={projectId} currency={currency} title={r.steps.assign} />
            {u ? <AssignTable v={u} set={set} /> : loading}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "run" && (
        <>
          <StepBody title={r.steps.run} lede={r.run.lede}>
            {running ? (
              <RunProgress job={v.job} lastSeconds={rc?.seconds ?? null} />
            ) : (
              <>
                {v.status === "failed" && v.job?.error && (
                  <p className="error" role="alert">
                    {t.step.failed} <span className="mono">{v.job.error}</span>
                  </p>
                )}
                {v.stale && <p className="wiz-warn">{r.run.stale}</p>}
                <ExcludedSince n={v.excluded_since} run={runIt} />
                {fresh && rc && (
                  <p className="wiz-ok">{r.run.ran({ when: when(rc.ran_at), seconds: rc.seconds })}</p>
                )}
                {!rc && <p className="wiz-from">{t.step.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: r.run.again, onPress: runIt }] : []}
            next={
              running
                ? { label: t.step.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? onward
                  : { label: rc ? r.run.againNext : r.run.next, disabled: act.isPending, onPress: runIt }
            }
          />
        </>
      )}
      {AFTER.includes(current) && rc && result && (
        <>
          <StepBody {...(current === "prices" ? {} : { title: r.steps[current] })}>
            {which}
            {v.stale && <p className="wiz-warn">{r.run.stale}</p>}
            <ExcludedSince n={v.excluded_since} run={runIt} />
            {/* Summary and On the map take the map over (SPEC §3.15): the ratios by group, the one whose Show on map
                was pressed (or picked on the map), else every group. */}
            {(current === "summary" || current === "map") && (
              <OnTheMap
                projectId={projectId}
                step={current === "map" ? r.steps.map : r.steps.summary}
                title={r.map.instruction}
                sub={r.map.instructionSub}
              >
                <RatioMap
                  projectId={projectId}
                  result={result}
                  currency={currency}
                  group={mapGroup}
                  setGroup={setStepPick}
                />
              </OnTheMap>
            )}
            {current === "summary" && (
              <Summary
                result={result}
                receipt={rc}
                nominal={nominal.length}
                see={() => go("extreme")}
                map={{ shown: mapGroup, show: setStepPick }}
              />
            )}
            {current === "prices" && (
              <>
                <OnTheMap
                  projectId={projectId}
                  step={r.steps.prices}
                  title={r.map.pricesInstruction}
                  sub={r.map.pricesInstructionSub}
                >
                  <RatioMap
                    projectId={projectId}
                    result={result}
                    currency={currency}
                    group={mapGroup}
                    setGroup={setStepPick}
                    bands
                  />
                </OnTheMap>
                <Prices projectId={projectId} result={result} currency={currency} />
              </>
            )}

            {current === "regions" && (
              <Regions
                projectId={projectId}
                result={result}
                setup={u}
                currency={currency}
                choose={(region) => change.mutate({ region }, { onSuccess: runIt })}
                busy={change.isPending || act.isPending}
              />
            )}
            {current === "similar" && (
              <>
                <OnTheMap
                  projectId={projectId}
                  step={r.steps.similar}
                  title={r.similar.mapInstruction}
                  sub={r.similar.mapInstructionSub}
                >
                  <SimilarMap projectId={projectId} result={result} group={mapGroup} setGroup={setStepPick} />
                </OnTheMap>
                <Similar result={result} map={{ shown: mapGroup, show: setStepPick }} />
              </>
            )}
            {current === "extreme" && (
              <>
                {result.trimmed.length > 0 && (
                  <OnTheMap
                    projectId={projectId}
                    step={r.steps.extreme}
                    title={r.extreme.mapInstruction}
                    sub={r.extreme.mapInstructionSub}
                  >
                    <ExtremeMap projectId={projectId} result={result} picked={mapGroup} pick={setStepPick} />
                  </OnTheMap>
                )}
                <Extreme
                  projectId={projectId}
                  result={result}
                  currency={currency}
                  map={{ shown: mapGroup, show: setStepPick }}
                />
              </>
            )}
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

/** Check the existing values, or skip to the models; which sets and which model groups. */
function WhatCard({ v, set }: CardProps) {
  const checking = v.check !== false;
  return (
    <div className="rv-cards">
      <Radios
        aria-label={r.what.title}
        className="cu-choices"
        value={checking ? "check" : "skip"}
        onChange={(x) => set({ check: x === "check" })}
      >
        {(["check", "skip"] as const).map((k) => (
          <Radio key={k} value={k} className="radio cu-choice">
            <span className="radio-dot" aria-hidden="true" />
            <span className="cu-text">
              <b>{r.what[k][0]}</b>
              <span className="cu-sub">{r.what[k][1]}</span>
            </span>
          </Radio>
        ))}
      </Radios>
      {checking && (
        <div className="wiz-grid rv-what">
          <span className="wiz-label">{r.what.sets}</span>
          <MultiPick
            label={r.what.sets}
            values={v.sets.map((x) => ({ value: x.id, label: x.name }))}
            chosen={v.chosen_sets}
            onChange={(sets) => set({ sets })}
            atLeastOne
          />
          <span />
          <span className="wiz-label">{r.what.groups}</span>
          <MultiPick
            label={r.what.groups}
            values={v.all_groups.map((g) => ({ value: g.value, label: g.label }))}
            chosen={v.chosen_groups}
            onChange={(groups) => set({ groups })}
            atLeastOne
          />
          <span />
        </div>
      )}
    </div>
  );
}

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
          <DateField
            label={r.sales.from}
            width="short"
            value={start}
            onChange={setStart}
            onCommit={(v) => commit("start", v)}
          />
          <DateField
            label={r.sales.to}
            width="short"
            value={end}
            onChange={setEnd}
            onCommit={(v) => commit("end", v)}
          />
        </div>
        {v.window_proposed ? (
          <p className="wiz-from">{r.sales.proposed({ start: v.proposed_start })}</p>
        ) : (
          <Button className="button button-small" onPress={() => set({ reset_window: true })}>
            {r.sales.reset}
          </Button>
        )}
        {v.year_before === 0 && v.last_sale && (
          <div className="bi-warn">{r.sales.none({ last: v.last_sale })}</div>
        )}
      </section>
      <section className="cs-step">
        <h3 className="wiz-group">{r.sales.price}</h3>
        <Radios
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
        </Radios>
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

/** The first page a board member can read: one paragraph, then a card per model group. */
function Summary({
  result,
  receipt,
  nominal,
  see,
  map,
}: {
  result: FieldResult;
  receipt: NonNullable<RatioView["receipt"]>;
  nominal: number;
  see: () => void;
  map: { shown: string; show: (id: string) => void };
}) {
  const [every, setEvery] = useState(false);
  const o = result.overall;
  const js = result.groups.filter(judged);
  const levelOk = js.filter((g) => g.verdict?.level);
  const lo = "90%";
  const hi = "110%";
  let text = o.median
    ? r.summary.head({ name: result.name, pct: pct(o.median), start: receipt.start, end: receipt.end })
    : "";
  if (js.length)
    text +=
      levelOk.length === 0
        ? r.summary.levelAll({ lo, hi })
        : levelOk.length === js.length
          ? r.summary.levelNone({ lo, hi })
          : r.summary.levelSome({ n: levelOk.length, of: js.length, lo, hi });
  const loose = js.filter((g) => g.verdict?.cod === false).map((g) => `${g.name} (COD ${num(g.cod, 1)})`);
  if (js.length) text += loose.length ? r.summary.notUniform({ names: loose.join(", ") }) : r.summary.uniform;
  const tight = js.filter((g) => g.verdict?.cod_low).map((g) => `${g.name} (COD ${num(g.cod, 1)})`);
  if (tight.length) text += r.summary.suspect({ names: tight.join(", ") });
  const tilted = js
    .filter((g) => g.vei_verdict === "regressive" || g.vei_verdict === "progressive")
    .map((g) => `${g.name} (${r.table.verdicts[g.vei_verdict ?? ""]})`);
  if (js.length)
    text += tilted.length ? r.summary.vertical({ names: tilted.join(", ") }) : r.summary.noVertical;
  const names = result.trimmed
    .filter((x) => x.nominal)
    .map((x) => x.address ?? x.key_sale)
    .slice(0, 4)
    .join(", ");
  return (
    <div className="rv-cards">
      <p className="rv-head">{text}</p>
      {/* As wide as its figures and words read; scrolls on its own when the page is narrower (a map docked). */}
      <div className="tbl-wrap">
        <Scorecard groups={result.groups} map={map} />
      </div>
      {/* Every figure (trimmed and not, the 90% range, PRD, MKI), folded away: was its own step, By model group. */}
      <Disclose open={every} onPress={() => setEvery(!every)}>
        {r.summary.everyFigure}
      </Disclose>
      {every && (
        <div className="tbl-wrap">
          <GroupsTable result={result} />
        </div>
      )}
      {nominal > 0 && (
        <div className="bi-warn">
          {r.summary.nominal({ n: nominal, names })}{" "}
          <Button className="wiz-link" onPress={see}>
            {r.summary.see}
          </Button>
        </div>
      )}
      <p className="wiz-from">
        {r.summary.ran({
          when: when(receipt.ran_at),
          n: o.sales,
          start: receipt.start,
          end: receipt.end,
          price: receipt.price === "sold" ? r.summary.asSold : r.summary.adjusted,
        })}
      </p>
    </div>
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
      <h2 className="wiz-q">{p.title({ name: g.name })}</h2>
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
              {p.vei({
                vei: g.vei == null ? "—" : `${signed(g.vei, 1)}%`,
                sig: g.vei_significance == null ? "—" : `${signed(g.vei_significance, 1)}%`,
                verdict: r.table.verdicts[g.vei_verdict ?? ""] ?? "—",
              })}
            </p>
            <BandChart series={[{ label: p.bySale, color: BY_SALE, bands: g.strata }]} />
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

function Similar({
  result,
  map,
}: {
  result: FieldResult;
  map: { shown: string; show: (id: string) => void };
}) {
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
            {/* Above the rows' Show on map: every group at once. */}
            <th className="rv-onmap">
              <ShowOnMapButton shown={map.shown === ""} onPress={() => map.show("")} label={r.map.allOnMap} />
            </th>
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
              <td className="rv-onmap">
                <ShowOnMapButton shown={map.shown === g.id} onPress={() => map.show(g.id)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

const LEAVE = ["ratio"] as const;

function Extreme({
  projectId,
  result,
  currency,
  map,
}: {
  projectId: string;
  result: FieldResult;
  currency: string;
  /** The sale on the map: its row's Show on map, or clicked there. */
  map: { shown: string; show: (key: string) => void };
}) {
  const [done, setDone] = useState<Set<string>>(new Set());
  // This step's results stay on screen, so several sales can be excluded in turn.
  const exclude = useMarkSale(projectId, LEAVE);
  const e = r.extreme;
  if (!result.trimmed.length) return <p className="wiz-from">{e.none}</p>;
  return (
    <>
      <p className="wiz-lede">{e.lede}</p>
      <div className="tbl-wrap tbl-natural">
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
              <th />
            </tr>
          </thead>
          <tbody>
            {result.trimmed.map((x) => (
              <tr key={x.key_sale} className={map.shown === x.key_sale ? "rv-picked" : undefined}>
                <td>{x.address ?? <Val v={x.key_sale} />}</td>
                <td>{x.group_name}</td>
                <td>{day(x.sale_date)}</td>
                <td className="cs-n">{money(x.price, currency)}</td>
                <td className="cs-n">{money(x.value, currency)}</td>
                <td className="cs-n">{num(x.ratio, x.ratio >= 100 ? 0 : 2)}</td>
                <td>{x.nominal ? e.nominal : x.ratio > 1 ? e.high : e.low}</td>
                <td className="rv-onmap">
                  <ShowOnMapButton shown={map.shown === x.key_sale} onPress={() => map.show(x.key_sale)} />
                </td>
                <td>
                  {done.has(x.key_sale) ? (
                    <span className="wiz-ok">{e.excluded}</span>
                  ) : (
                    <Button
                      className="button button-small"
                      isDisabled={exclude.isPending}
                      onPress={() =>
                        exclude.mutate(
                          {
                            key: x.key_sale,
                            action: "exclude",
                            note: x.nominal ? e.note({ price: money(x.price, currency) }) : "",
                          },
                          { onSuccess: () => setDone((d) => new Set(d).add(x.key_sale)) },
                        )
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
      </div>
      {exclude.error && (
        <p className="error" role="alert">
          {exclude.error.message}
        </p>
      )}
    </>
  );
}
