import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";
import {
  api,
  type Project,
  type Scale,
  type Source,
  unwrap,
  type Wizard,
  type WizardField,
  type WizardStep,
} from "../api/client";
import { ToolButton } from "../components/Buttons";
import { Seg } from "../components/Seg";
import { Val } from "../components/Val";
import { amount, short } from "../lib/format";
import { say, t } from "../wording";
import { FieldRow } from "./FieldRow";
import { PAIRS, SCALED } from "./Quality";
import type { MutateAsync } from "./wizardChange";

const q = t.wizard.quality;
type As = "num" | "cat";
const TIERS: Scale = { kind: "tiers", fraction: false, low: null, high: null, tiers: {} };
// A tier (or band) with fewer sales than this isn't held to selling for more than the one below it.
const FEW = 10;

/** Quality or condition: one column the models use, which the user says is numbers or categories. Numbers: which
 * way is better (or what they mean), with what each value sold for, live. Categories: its tiers ranked, best at
 * the top, each given a number. The category's text follows a category column, for reports. */
export function QualityStep({
  project,
  data,
  step,
  change,
}: {
  project: Project;
  data: Wizard;
  step: WizardStep;
  change: MutateAsync;
}) {
  const num = data.fields.find((f) => f.key === step.fields.find((k) => SCALED.includes(k)));
  const txt = data.fields.find((f) => f.key === PAIRS[num?.key ?? ""]);
  const source = num?.sources[0];
  const derived: As | null = num?.scale?.kind === "tiers" ? "cat" : source ? "num" : null;
  const [pref, setPref] = useState<As | null>(null);
  if (!num) return null;
  const as: As = pref ?? derived ?? "num";
  // A column the file writes as text can't be read as numbers: say so, rather than read it wrongly.
  const mismatch = as === "num" && !!source && num.numbers === false;
  const choose = (next: As) => {
    setPref(next);
    if (!source) return;
    if (next === "cat" && num.scale?.kind !== "tiers")
      void change({
        kind: "field",
        key: num.key,
        file: source.file,
        column: source.column,
        scale: TIERS,
      }).catch(() => {});
    if (next === "num" && num.scale?.kind === "tiers" && num.numbers)
      void change({
        kind: "field",
        key: num.key,
        file: source.file,
        column: source.column,
        scale: { ...TIERS, kind: null },
      }).catch(() => {});
  };
  // The text loaded from a column of its own (an earlier choice) still shows: nothing loaded is out of sight.
  const ownText = !!txt?.sources[0] && txt.sources[0].column !== source?.column;
  // Only the universe so far: building details are often in a separate file (a CAMA export).
  const onlyBase = data.files.filter((f) => f.holds === "parcels").length <= 1;
  return (
    <>
      {onlyBase && <p className="wiz-note wiz-another">{t.wizard.anotherFileHint}</p>}
      <div className="wiz-grid frame">
        <div className="wiz-label">{q.writtenAsLabel}</div>
        <div className="wiz-span seg-row">
          <Seg
            label={q.writtenAsLabel}
            value={as}
            options={(["num", "cat"] as const).map((k) => [k, q.asKinds[k]] as const)}
            onChange={choose}
          />
          {mismatch && source ? (
            <span className="wiz-warn">⚠ {q.notNumbers({ column: source.column })}</span>
          ) : (
            <span className="wiz-from">{q.asHints[as]}</span>
          )}
        </div>
        <FieldRow
          project={project}
          data={data}
          field={num}
          sales={false}
          change={change}
          label={q.column}
          onPage
          pickScale={as === "cat" ? TIERS : undefined}
        />
        {ownText && txt && (
          <FieldRow project={project} data={data} field={txt} sales={false} change={change} onPage />
        )}
      </div>
      {source && !mismatch && as === "num" && num.scale?.kind && num.scale.kind !== "tiers" && (
        <Evidence projectId={project.id} field={num} source={source} />
      )}
      {source && as === "cat" && num.scale?.kind === "tiers" && (
        <TiersPanel projectId={project.id} field={num} source={source} change={change} />
      )}
    </>
  );
}

/** A bar and its amount: as long as its share of the longest. */
function Bar({ v, top, symbol }: { v: number | null | undefined; top: number; symbol: string }) {
  if (v == null) return null;
  return (
    <>
      <span className="qc-bar" style={{ width: `${(6 * v) / top}rem` }} />
      {amount(symbol, v)}
    </>
  );
}

/** Steps up (from worse to better, each with enough sales) whose median falls. */
function stepsDown(medians: (readonly [number, number | null | undefined])[]): number {
  let last: number | null = null;
  let down = 0;
  for (const [sales, m] of medians) {
    if (m == null || sales < FEW) continue;
    if (last != null && m < last) down += 1;
    last = m;
  }
  return down;
}

/** What each value sold for, as the column is read now (higher is better): changes as soon as the way is chosen. */
function Evidence({ projectId, field, source }: { projectId: string; field: WizardField; source: Source }) {
  const scale = field.scale;
  const preview = useQuery({
    queryKey: ["scale", projectId, field.key, source.file, source.column, scale?.kind, scale?.fraction],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/fields/{key}/scale", {
          params: { path: { project_id: projectId, key: field.key } },
          body: { file: source.file, column: source.column, scale: scale ?? null },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = preview.data;
  if (!v) return null;
  const bands = v.by_value;
  const topPrice = Math.max(1, ...bands.map((b) => b.price ?? 0));
  const topArea = Math.max(1, ...bands.map((b) => b.per_area ?? 0));
  const texts = bands.some((b) => b.text);
  const down = stepsDown(bands.map((b) => [b.sales, b.price] as const));
  const condition = field.key === "bldg_condition_num";
  const told = v.fits.length > 0 && v.by_age.filter((b) => b.count >= 5).length > 1;
  const newer = told && !!scale?.kind && v.fits.includes(scale.kind);
  return (
    <div className="frame qc-panel">
      <h3 className="wiz-group">{q.evidenceHead}</h3>
      {condition && told && (
        <div className={`rc-meter ${newer ? "ok" : "bad"}`}>
          <b>{newer ? q.newerBetter : `⚠ ${q.olderBetter}`}</b>
        </div>
      )}
      {bands.length > 0 && (
        <>
          <div className={`rc-meter ${down ? "bad" : "ok"}`}>
            <b>{down ? `⚠ ${q.fallsPrice({ n: down })}` : q.risesPrice}</b>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>{q.asReadBand}</th>
                {texts && <th>{q.writtenText}</th>}
                <th className="num">{q.sales}</th>
                <th>{q.medianPrice}</th>
                {v.price_basis && <th>{q.medianOf({ basis: v.price_basis })}</th>}
              </tr>
            </thead>
            <tbody>
              {/* Best at the top, as the tiers are. */}
              {[...bands].reverse().map((b) => (
                <tr key={b.label}>
                  <td className="mono">{b.label}</td>
                  {texts && <td className="mono">{b.text}</td>}
                  <td className="num">{b.sales.toLocaleString()}</td>
                  <td>
                    <Bar v={b.price} top={topPrice} symbol={v.symbol} />
                  </td>
                  {v.price_basis && (
                    <td>
                      <Bar v={b.per_area} top={topArea} symbol={v.symbol} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="rc-sub">{say.wizard.quality.byPriceLede(v.by_type, v.type_field)}</p>
        </>
      )}
      {v.samples.length > 0 && (
        <p className="rc-sub mono">
          {q.samplesLine}{" "}
          {v.samples.map((s) => `${short(s.raw)} → ${s.value.toLocaleString()}`).join("  ·  ")}
        </p>
      )}
      {v.notes.length > 0 && <p className="rc-sub">{v.notes.join(" · ")}</p>}
    </div>
  );
}

/** A category's tiers, best at the top, each with its number and what it sold for. Every move is saved. */
function TiersPanel({
  projectId,
  field,
  source,
  change,
}: {
  projectId: string;
  field: WizardField;
  source: Source;
  change: MutateAsync;
}) {
  const saved = field.scale?.tiers ?? {};
  const preview = useQuery({
    queryKey: ["tiers", projectId, field.key, source.file, source.column, JSON.stringify(saved)],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/fields/{key}/tiers", {
          params: { path: { project_id: projectId, key: field.key } },
          body: { file: source.file, column: source.column },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = preview.data;
  if (!v) return null;
  const used = v.saved;
  // Worst to best, as the server orders them; the table shows best first.
  const worstFirst = v.tiers;
  const save = (order: string[]) =>
    void change({
      kind: "field",
      key: field.key,
      file: source.file,
      column: source.column,
      scale: { ...TIERS, tiers: Object.fromEntries(order.map((x, i) => [x, i + 1])) },
    }).catch(() => {});
  // Up the table is better: one place further along worst-to-best.
  const move = (value: string, by: number) => {
    const order = worstFirst.map((x) => x.value);
    const i = order.indexOf(value);
    const j = i + by;
    if (i < 0 || j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j] as string, order[i] as string];
    save(order);
  };
  const perArea = v.basis !== null && v.basis !== "sale price";
  const rows = [...worstFirst].reverse();
  const topPrice = Math.max(1, ...rows.map((r) => r.price ?? 0));
  const topArea = Math.max(1, ...rows.map((r) => r.median ?? 0));
  const priced = rows.some((r) => r.price != null);
  // A tier ranked above another (enough sales each) that sells for less per area: said beside it.
  const flags: Record<string, string> = {};
  let last: (typeof worstFirst)[number] | null = null;
  for (const r of worstFirst) {
    if (r.median == null) continue;
    if (r.sales < v.few) {
      flags[r.value] = q.fewSales({ n: r.sales });
      continue;
    }
    if (last?.median != null && r.median < last.median) flags[r.value] = q.sellsForLess({ v: last.value });
    last = r;
  }
  const down = stepsDown(worstFirst.map((r) => [r.sales, r.median] as const));
  return (
    <div className="frame qc-panel">
      <h3 className="wiz-group">{q.tiersHead}</h3>
      <p className="rc-sub">{q.tiersHint}</p>
      <div className="qc-row">
        {used ? (
          <span className="pill">{q.savedOrder}</span>
        ) : v.recognised ? (
          <span className="pill pill-ok">{q.recognised({ name: v.recognised })}</span>
        ) : (
          <span className="pill pill-warn">{q.notRecognised}</span>
        )}
        {!used && <span className="wiz-warn">{q.suggested}</span>}
      </div>
      {priced && (
        <div className={`rc-meter ${down ? "bad" : "ok"}`}>
          <b>
            {down
              ? `⚠ ${q.stepsDown({ n: down, basis: v.basis ?? "" })}`
              : say.wizard.quality.rises(v.basis ?? "")}
          </b>
        </div>
      )}
      <table className="tbl qc-tiers">
        <thead>
          <tr>
            <th>{q.tier}</th>
            <th className="num">{q.number}</th>
            <th className="num">{q.buildings}</th>
            {priced && <th className="num">{q.sales}</th>}
            {priced && <th>{q.medianPrice}</th>}
            {priced && perArea && <th>{q.medianOf({ basis: v.basis ?? "" })}</th>}
            <th />
            <th />
          </tr>
        </thead>
        <tbody>
          <tr className="qc-end">
            <td colSpan={8}>{q.best}</td>
          </tr>
          {rows.map((r, i) => {
            const unplaced = !used && v.unplaced.includes(r.value);
            const note = unplaced ? q.placeIt : r.number == null ? q.notRanked : flags[r.value];
            return (
              <tr key={r.value} className={flags[r.value] && r.sales >= v.few ? "qc-bad" : undefined}>
                <td className="mono">
                  <Val v={r.value} />
                </td>
                <td className="num qc-rank">{r.number == null ? "–" : r.number.toLocaleString()}</td>
                <td className="num">{r.count.toLocaleString()}</td>
                {priced && <td className="num">{r.sales.toLocaleString()}</td>}
                {priced && (
                  <td>
                    <Bar v={r.price} top={topPrice} symbol={v.symbol} />
                  </td>
                )}
                {priced && perArea && (
                  <td>
                    <Bar v={r.median} top={topArea} symbol={v.symbol} />
                  </td>
                )}
                <td className="qc-flag">{note ? `⚠ ${note}` : ""}</td>
                <td className="qc-arrows">
                  <ToolButton
                    label={q.up({ v: r.value })}
                    isDisabled={i === 0}
                    onPress={() => move(r.value, 1)}
                  >
                    <ArrowUp aria-hidden="true" size="1em" />
                  </ToolButton>
                  <ToolButton
                    label={q.down({ v: r.value })}
                    isDisabled={i === rows.length - 1}
                    onPress={() => move(r.value, -1)}
                  >
                    <ArrowDown aria-hidden="true" size="1em" />
                  </ToolButton>
                </td>
              </tr>
            );
          })}
          <tr className="qc-end">
            <td colSpan={8}>{q.worst}</td>
          </tr>
        </tbody>
      </table>
      {v.notes.length > 0 && <p className="rc-sub">{v.notes.join(" · ")}</p>}
      {!used && (
        <div className="form-actions">
          <Button className="button button-primary" onPress={() => save(worstFirst.map((x) => x.value))}>
            {q.useOrder}
          </Button>
        </div>
      )}
    </div>
  );
}
