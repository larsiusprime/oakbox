import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, Heading, Input, Modal, ModalOverlay, TextField } from "react-aria-components";
import { api, type Scale, type Source, unwrap, type Wizard, type WizardField } from "../api/client";
import { Choice } from "../components/Form";
import { Val } from "../components/Val";
import { amount, pct, short } from "../lib/format";
import { t } from "../strings";

const q = t.wizard.quality;
type Kind = NonNullable<Scale["kind"]>;
export const SCALED = ["bldg_quality_num", "bldg_condition_num"];
export const PAIRS: Record<string, string> = {
  bldg_quality_num: "bldg_quality_txt",
  bldg_quality_txt: "bldg_quality_num",
  bldg_condition_num: "bldg_condition_txt",
  bldg_condition_txt: "bldg_condition_num",
};
const KINDS: Record<string, Kind[]> = {
  bldg_quality_num: ["higher", "lower"],
  bldg_condition_num: ["pct_good", "pct_depr", "higher", "lower", "life"],
};
const NONE = "__none";
export const ABSENT = "__absent";

/** What a change to a quality/condition field sends (FieldsWizard's field change). */
export type QualityChange = {
  key: string;
  file?: string | null;
  column?: string | null;
  scale?: Scale;
  absent?: boolean;
};

/** The meaning of a quality/condition number, beside its column: which way it runs, or what it measures. */
export function ScaleChoice({
  field,
  source,
  change,
}: {
  field: WizardField;
  source: Source;
  change: (c: QualityChange) => void;
}) {
  const kinds = KINDS[field.key] ?? [];
  const scale = field.scale;
  if (!scale || scale.kind === "tiers") return null;
  return (
    <div className="wiz-unit">
      <Choice
        label={q.meaningOf(field.name)}
        hideLabel
        value={scale.kind ?? null}
        placeholder={field.key === "bldg_quality_num" ? q.whichWay : q.means}
        options={kinds.map((k) => [k, q.kinds[k] ?? k] as const)}
        onChange={(kind) =>
          change({ key: field.key, file: source.file, column: source.column, scale: { ...scale, kind } })
        }
      />
    </div>
  );
}

function fmt(v: number | null | undefined): string {
  if (v == null) return "";
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** Columns that look like quality or condition, side by side, to choose the number and the category from. */
export function CompareDialog({
  projectId,
  data,
  numKey,
  close,
  save,
}: {
  projectId: string;
  data: Wizard;
  numKey: string;
  close: () => void;
  save: (num: QualityChange, txt: QualityChange) => void;
}) {
  const txtKey = PAIRS[numKey] ?? "";
  const list = useQuery({
    queryKey: ["candidates", projectId, numKey],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/fields/{key}/candidates", {
          params: { path: { project_id: projectId, key: numKey } },
        }),
      ),
  });
  const field = (k: string) => data.fields.find((f) => f.key === k);
  const at = (k: string) => {
    const f = field(k);
    const s = f?.sources[0];
    return f?.absent ? ABSENT : s ? `${s.file}\u0000${s.column}` : NONE;
  };
  const [num, setNum] = useState(at(numKey));
  const [txt, setTxt] = useState(at(txtKey));
  const rows = list.data ?? [];
  const options = rows.map((c) => [`${c.file}\u0000${c.column}`, `${c.column} · ${c.file}`] as const);
  const condition = numKey === "bldg_condition_num";
  const as = (v: string, key: string): QualityChange => {
    if (v === ABSENT) return { key, absent: true };
    if (v === NONE) return { key };
    const [file, column] = v.split("\u0000");
    return { key, file: file ?? null, column: column ?? null };
  };
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rl qc">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {condition ? q.compareCondition : q.compareQuality}
          </Heading>
          <p className="rc-sub">{q.compareLede}</p>
          {list.isPending ? (
            <p className="rc-sub">{q.loading}</p>
          ) : rows.length === 0 ? (
            <p className="rc-sub">{condition ? q.noneConditionLike : q.noneQualityLike}</p>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>{q.column}</th>
                  <th>{q.looksLike}</th>
                  <th>{q.filled}</th>
                  <th>{q.values}</th>
                  <th>{q.samples}</th>
                  <th>{q.notes}</th>
                  <th>{q.loadedAs}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={`${c.file}/${c.column}`} className={c.loaded_as ? "on" : undefined}>
                    <td className="mono">
                      {c.column} <span className="wiz-from">· {c.file}</span>
                    </td>
                    <td>{c.kind === "numbers" ? q.numbers(fmt(c.low), fmt(c.high)) : q.text}</td>
                    <td>{pct(c.filled)}</td>
                    <td>{c.distinct.toLocaleString()}</td>
                    <td className="mono">{c.samples.map((x) => short(x)).join(", ")}</td>
                    <td className={c.warn ? "qc-flag" : undefined}>{c.notes.join(" · ")}</td>
                    <td>
                      {c.loaded_as && <span className="pill pill-ok">{q.loadedAsWord[c.loaded_as]}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="qc-row">
            <b>{q.number}</b>
            <Choice
              label={q.number}
              hideLabel
              value={num}
              options={[
                [NONE, t.wizard.none] as const,
                ...options,
                ...(condition ? [[ABSENT, q.absent] as const] : []),
              ]}
              onChange={setNum}
            />
            <b>{q.category}</b>
            <Choice
              label={q.category}
              hideLabel
              value={txt}
              options={[[NONE, t.wizard.none] as const, ...options]}
              onChange={setTxt}
            />
          </div>
          <p className="rc-sub">{q.preferNumber}</p>
          {list.error && (
            <p className="error" role="alert">
              {list.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {q.cancel}
            </Button>
            <Button className="button button-primary" onPress={() => save(as(num, numKey), as(txt, txtKey))}>
              {q.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** What a quality or condition number means: checked against age (newer should be better) and price. */
export function ScaleDialog({
  projectId,
  field,
  source,
  close,
  save,
}: {
  projectId: string;
  field: WizardField;
  source: Source;
  close: () => void;
  save: (scale: Scale) => void;
}) {
  const [kind, setKind] = useState<Kind | null>(field.scale?.kind ?? null);
  const [fraction, setFraction] = useState(field.scale?.fraction ?? false);
  const asked: Scale = { kind, fraction, low: null, high: null, tiers: {} };
  const preview = useQuery({
    queryKey: ["scale", projectId, field.key, source.file, source.column, kind, fraction],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/fields/{key}/scale", {
          params: { path: { project_id: projectId, key: field.key } },
          body: { file: source.file, column: source.column, scale: asked },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = preview.data;
  const condition = field.key === "bldg_condition_num";
  const pctKind = kind === "pct_good" || kind === "pct_depr";
  // Newer buildings should come out better as read: each older band no better than the one before.
  const ages = v?.by_age.filter((b) => b.count >= 5) ?? [];
  const falls = ages.every((b, i) => i === 0 || (b.value ?? 0) <= (ages[i - 1]?.value ?? 0) + 0.5);
  const top = Math.max(1, ...(v?.by_age.map((b) => Math.abs(b.value ?? 0)) ?? []));
  const topPrice = Math.max(1, ...(v?.by_value.map((b) => b.value ?? 0) ?? []));
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rl qc">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {condition ? q.meaningTitle(source.column) : q.directionTitle(source.column)}
          </Heading>
          <p className="rc-sub">{condition ? q.meaningLede : q.directionLede}</p>
          <ul className="qc-radio" aria-label={q.meaningOf(field.name)}>
            {(v?.kinds ?? KINDS[field.key] ?? []).map((k) => (
              <li key={k} className={k === kind ? "on" : undefined}>
                <Button className="qc-pick" onPress={() => setKind(k as Kind)} aria-pressed={k === kind}>
                  <span className="dot" />
                  <span>
                    <b>{q.kinds[k]}</b> <small>{q.kindHints[k]}</small>
                  </span>
                  {v?.fits.includes(k) && v.age_basis && <span className="tag">✓ {q.fits(v.age_basis)}</span>}
                </Button>
              </li>
            ))}
          </ul>
          {pctKind && (
            <div className="qc-row">
              <span>{q.writtenAs}</span>
              <Choice
                label={q.writtenAs}
                hideLabel
                value={fraction ? "f" : "p"}
                options={[
                  ["f", q.fractions],
                  ["p", q.percents],
                ]}
                onChange={(x) => setFraction(x === "f")}
              />
              {v && <span className="wiz-from">{q.found(fmt(v.scale.low), fmt(v.scale.high))}</span>}
            </div>
          )}
          {v && kind && condition && ages.length > 1 && (
            <div className={`rc-meter ${falls ? "ok" : "bad"}`}>
              <b>{falls ? q.newerBetter : q.olderBetter}</b>
              {v.median != null && <span className="rc-was">{q.median(fmt(v.median))}</span>}
            </div>
          )}
          {v && condition && v.by_age.length > 0 && (
            <table className="tbl">
              <thead>
                <tr>
                  <th>{v.age_basis === "effective age" ? q.effectiveAge : q.age}</th>
                  <th>{q.buildings}</th>
                  <th>{q.asWritten}</th>
                  <th>{q.asRead}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {v.by_age.map((b) => (
                  <tr key={b.label}>
                    <td>{b.label}</td>
                    <td>{b.count.toLocaleString()}</td>
                    <td className="mono">{fmt(b.raw)}</td>
                    <td className="mono">{kind ? fmt(b.value) : ""}</td>
                    <td>
                      {kind && (
                        <span
                          className="qc-bar"
                          style={{ width: `${(8 * Math.abs(b.value ?? 0)) / top}rem` }}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {v && v.by_value.length > 0 && (
            <table className="tbl">
              <thead>
                <tr>
                  <th>{q.asReadBand}</th>
                  <th>{q.sales}</th>
                  <th>{q.medianOf(v.price_basis ?? "")}</th>
                </tr>
              </thead>
              <tbody>
                {v.by_value.map((b) => (
                  <tr key={b.label}>
                    <td>{b.label}</td>
                    <td>{b.count.toLocaleString()}</td>
                    <td>
                      <span className="qc-bar" style={{ width: `${(8 * (b.value ?? 0)) / topPrice}rem` }} />
                      {b.value != null ? amount(v.symbol, b.value) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {v && v.notes.length > 0 && <p className="rc-sub">{v.notes.join(" · ")}</p>}
          {v && kind && v.samples.length > 0 && (
            <p className="rc-sub mono">
              {v.samples.map((s) => `${short(s.raw)} → ${fmt(s.value)}`).join("  ·  ")}
            </p>
          )}
          <details className="rc-writes">
            <summary>{q.writes}</summary>
            <pre>
              {!kind
                ? q.nothingYet
                : v?.calc
                  ? `"load": { "${field.key}_src": ["${source.column}", "float"] }\n"calc": { "${field.key}": ${JSON.stringify(v.calc)} }`
                  : `"load": { "${field.key}": ["${source.column}", "float"] }`}
            </pre>
          </details>
          {preview.error && (
            <p className="error" role="alert">
              {preview.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {q.cancel}
            </Button>
            <Button className="button button-primary" isDisabled={!kind} onPress={() => save(asked)}>
              {q.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

type Row = { value: string; count: number; number: string; sales: number; median: number | null };

/** A category's tiers, worst to best, each with a number: equal steps unless typed otherwise. */
export function TiersDialog({
  projectId,
  field,
  source,
  close,
  save,
}: {
  projectId: string;
  field: WizardField;
  source: Source;
  close: () => void;
  save: (tiers: Record<string, number>) => void;
}) {
  const preview = useQuery({
    queryKey: ["tiers", projectId, field.key, source.file, source.column],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/fields/{key}/tiers", {
          params: { path: { project_id: projectId, key: field.key } },
          body: { file: source.file, column: source.column },
        }),
      ),
  });
  const v = preview.data;
  // The user's edits, over the order and numbers as loaded (saved or suggested).
  const [edited, setRows] = useState<Row[] | null>(null);
  const rows =
    edited ?? v?.tiers.map((x) => ({ ...x, number: x.number == null ? "" : String(x.number) })) ?? null;
  const steps = (list: Row[]) => list.map((r, i) => ({ ...r, number: String(i + 1) }));
  const move = (i: number, by: number) => {
    if (!rows) return;
    const j = i + by;
    if (j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[i], next[j]] = [next[j] as Row, next[i] as Row];
    setRows(steps(next));
  };
  const few = v?.few ?? 10;
  // Out of order: a tier ranked above another (with enough sales each) that sells for less.
  const flags: Record<string, string> = {};
  let last: Row | null = null;
  let down = 0;
  for (const r of rows ?? []) {
    if (r.median == null) continue;
    if (r.sales < few) {
      flags[r.value] = q.fewSales(r.sales);
      continue;
    }
    if (last?.median != null && r.median < last.median) {
      flags[r.value] = q.sellsForLess(last.value);
      down += 1;
    }
    last = r;
  }
  const top = Math.max(1, ...(rows ?? []).map((r) => r.median ?? 0));
  const valid =
    !!rows && rows.length > 0 && rows.every((r) => r.number.trim() !== "" && !Number.isNaN(Number(r.number)));
  const priced = (rows ?? []).some((r) => r.median != null);
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rl qc">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {q.tiersTitle(source.column)}
          </Heading>
          <p className="rc-sub">{q.tiersLede(source.column)}</p>
          {v && (
            <div className="qc-row">
              {v.saved ? (
                <span className="pill">{q.savedOrder}</span>
              ) : v.recognised ? (
                <span className="pill pill-ok">{q.recognised(v.recognised)}</span>
              ) : (
                <span className="pill pill-warn">{q.notRecognised}</span>
              )}
              {v.unplaced.length > 0 && v.recognised && !v.saved && (
                <span className="qc-flag">{q.unplaced(v.unplaced.map((x) => short(x)).join(", "))}</span>
              )}
              <Button className="button" onPress={() => rows && setRows(steps([...rows].reverse()))}>
                {q.reverse}
              </Button>
              <Button className="button" onPress={() => rows && setRows(steps(rows))}>
                {q.equalSteps}
              </Button>
            </div>
          )}
          {rows && (
            <table className="tbl">
              <thead>
                <tr>
                  <th />
                  <th>{q.tier}</th>
                  <th>{q.rows}</th>
                  <th>{q.number}</th>
                  {priced && <th>{q.sales}</th>}
                  {priced && <th>{q.medianOf(v?.basis ?? "")}</th>}
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.value} className={flags[r.value] && r.sales >= few ? "qc-bad" : undefined}>
                    <td className="qc-arrows">
                      <Button
                        className="qc-move"
                        aria-label={q.up(r.value)}
                        isDisabled={i === 0}
                        onPress={() => move(i, -1)}
                      >
                        <ArrowUp size="0.85em" />
                      </Button>
                      <Button
                        className="qc-move"
                        aria-label={q.down(r.value)}
                        isDisabled={i === rows.length - 1}
                        onPress={() => move(i, 1)}
                      >
                        <ArrowDown size="0.85em" />
                      </Button>
                    </td>
                    <td className="mono">
                      <Val v={r.value} />
                    </td>
                    <td>{r.count.toLocaleString()}</td>
                    <td className="num">
                      <TextField
                        aria-label={q.numberFor(r.value)}
                        value={r.number}
                        onChange={(x) =>
                          setRows(rows.map((y) => (y.value === r.value ? { ...y, number: x } : y)))
                        }
                      >
                        <Input className="input qc-num" />
                      </TextField>
                    </td>
                    {priced && <td>{r.sales.toLocaleString()}</td>}
                    {priced && (
                      <td>
                        {r.median != null && v && (
                          <>
                            <span className="qc-bar" style={{ width: `${(8 * r.median) / top}rem` }} />
                            {amount(v.symbol, r.median)}
                          </>
                        )}
                      </td>
                    )}
                    <td className="qc-flag">{flags[r.value] ? `⚠ ${flags[r.value]}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {v && priced && (
            <div className={`rc-meter ${down ? "bad" : "ok"}`}>
              <b>{down ? q.stepsDown(down, v.basis ?? "") : q.rises(v.basis ?? "")}</b>
              <span className="rc-was">{q.evidenceOnly}</span>
            </div>
          )}
          {v && v.notes.length > 0 && <p className="rc-sub">{q.basedOn(v.notes.join(" · "))}</p>}
          {preview.error && (
            <p className="error" role="alert">
              {preview.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {q.cancel}
            </Button>
            <Button
              className="button button-primary"
              isDisabled={!valid}
              onPress={() => rows && save(Object.fromEntries(rows.map((r) => [r.value, Number(r.number)])))}
            >
              {q.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
