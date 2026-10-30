import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";
import type { CorrDetail, ModelPatch, ModelSetup, TestRow, VarTestView } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { num } from "../lib/format";
import { t } from "../strings";
import { ColumnsNote } from "./Models";

const vt = t.values.vartest;

/** How each test's figure reads: as a share, a score, a coefficient, a p-value; and which way is better. */
const LOWER_BETTER = new Set(["p_value", "vif"]);

function figure(test: string, v: number | null | undefined): string {
  if (v == null) return "—";
  if (test === "represented") return `${Math.round(100 * v)}%`;
  if (test === "p_value") return v < 0.001 ? "< 0.001" : num(v, 3);
  if (test === "corr") return num(v, 3);
  return num(v, 2);
}

/** One test, one model group: a row per variable (a category's values each on their own row), its result as a bar
 * against the test's threshold, pass or fail, and a tick to keep the variable. */
export function TestStep({
  test,
  view,
  setup,
  set,
  fill,
}: {
  test: string;
  view: VarTestView;
  setup: ModelSetup;
  set: (body: ModelPatch) => void;
  fill: () => void;
}) {
  const r = view.receipt;
  const tested = (r?.groups ?? []).filter((g) => Object.keys(g.tests).length > 0);
  const [gid, setGid] = useState(() => [...tested].sort((a, b) => b.sales - a.sales)[0]?.id ?? "");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [how, setHow] = useState<Set<string>>(() => new Set());
  const flip = (column: string) =>
    setHow((was) => {
      const now = new Set(was);
      if (now.has(column)) now.delete(column);
      else now.add(column);
      return now;
    });
  if (!r) return null;
  const g = tested.find((x) => x.id === gid) ?? tested[0];
  const info = vt.tests[test];
  const key = vt.thresholdKey[test];
  const threshold = key ? r.thresholds[key] : undefined;
  const rule = info ? (typeof info.rule === "function" ? info.rule(threshold ?? 0) : info.rule) : "";
  const rows = [...(g?.tests[test] ?? [])];
  const val = (x: TestRow) => x.value;
  rows.sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    if (va == null || vb == null) return va == null ? 1 : -1;
    return LOWER_BETTER.has(test) ? va - vb : vb - va;
  });
  const top = Math.max(
    ...rows.map((x) => val(x) ?? 0),
    test === "vif" ? 2 * (threshold ?? 10) : 0,
    threshold ?? 0,
    test === "vif" ? 0 : 1,
    1e-9,
  );
  // VIF runs from 1 to the thousands: on a log scale, so the threshold and the ones near it can be read.
  const width = (v: number | null) =>
    v == null
      ? 0
      : test === "vif"
        ? Math.max(0, Math.min(100, (100 * Math.log10(Math.max(v, 1))) / Math.log10(Math.max(top, 10))))
        : Math.max(0, Math.min(100, (100 * v) / top));
  const chosen = setup.variables.filter((x) => x.chosen).map((x) => x.field);
  const names = Object.fromEntries(setup.variables.map((x) => [x.field, x.name]));
  // A category is one row, its values (each its own column to the tests) folded under it, best first: it passes if
  // any of its values does.
  const items: { variable: string; category: boolean; rows: TestRow[] }[] = [];
  for (const x of rows) {
    const it = items.find((y) => y.variable === x.variable);
    if (it) it.rows.push(x);
    else items.push({ variable: x.variable, category: x.level != null, rows: [x] });
  }
  const cells = (passed: boolean | null | undefined, x: TestRow) => (
    <>
      <td className="cs-n">
        <span className="rv-cell">
          <span className="rv-cell-pill">
            {passed == null ? null : (
              <span className={passed ? "rv-pill rv-ok" : "rv-pill rv-bad"}>
                {passed ? `✓ ${vt.pass}` : `✗ ${x.reason ? vt.reasons[x.reason] : vt.fail}`}
              </span>
            )}
          </span>
          <span>
            {x.reason === "no_correlation"
              ? vt.withPrice(num(x.more.corr_strength, 3))
              : figure(test, x.value)}
          </span>
        </span>
      </td>
      <td className="vt-bar-cell">
        <span className="vt-bar">
          <span
            className={passed === false ? "vt-fill vt-fill-bad" : "vt-fill"}
            style={{ width: `${width(val(x))}%` }}
          />
          {threshold != null && <span className="vt-mark" style={{ left: `${width(threshold)}%` }} />}
        </span>
      </td>
    </>
  );
  const failingVars = [...new Set(rows.filter((x) => x.passed === false).map((x) => x.variable))].filter(
    (v) => !rows.some((x) => x.variable === v && x.passed),
  );
  const failingTicked = failingVars.filter((v) => chosen.includes(v));
  return (
    <div className="cs-step">
      <p className="wiz-lede">{info?.lede}</p>
      <div className="cs-row">
        <Choice
          label={vt.group}
          value={g?.id ?? ""}
          options={tested.map(
            (x) => [x.id, `${x.name} · ${t.values.model.salesCount(x.sales)}`] as [string, string],
          )}
          onChange={setGid}
        />
        <span className="wiz-from">{rule}</span>
      </div>
      {g && g.empty.length > 0 && (
        <p className="wiz-warn">
          {vt.empty(g.empty.map((f) => names[f] ?? f))}{" "}
          <Button className="wiz-link" onPress={fill}>
            {t.values.model.fillIt}
          </Button>
        </p>
      )}
      {r.groups.some((x) => x.skipped) && (
        <p className="wiz-from">
          {r.groups
            .filter((x) => x.skipped)
            .map((x) => vt.skipped(x.name, x.skipped ?? ""))
            .join(" ")}
        </p>
      )}
      <p className={failingVars.length ? "wiz-warn" : "wiz-ok"}>
        {failingVars.length ? vt.failing(failingVars.length) : vt.noneFail}{" "}
        {failingTicked.length > 0 && (
          <Button
            className="wiz-link"
            onPress={() => set({ variables: chosen.filter((v) => !failingTicked.includes(v)) })}
          >
            {vt.untickFailing}
          </Button>
        )}
      </p>
      <table className="bi-tbl cs-tbl vt-tbl">
        <thead>
          <tr>
            <th>{vt.variable}</th>
            <th className="cs-n">{info?.figure}</th>
            <th>{vt.value}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, k) => {
            const best = it.rows[0];
            if (!best) return null;
            const firstWeak =
              test === "corr" &&
              it.rows.every((x) => x.reason === "no_correlation") &&
              !items.slice(0, k).some((y) => y.rows.every((x) => x.reason === "no_correlation"));
            const ticked = chosen.includes(it.variable);
            const shown = open.has(it.variable);
            const passing = it.rows.filter((x) => x.passed).length;
            const Chevron = shown ? ChevronDown : ChevronRight;
            return [
              ...(firstWeak
                ? [
                    <tr key="weak-band" className="bi-grp">
                      <td colSpan={3}>{vt.firstPass(vt.floor)}</td>
                    </tr>,
                  ]
                : []),
              <tr key={it.variable} className={ticked ? undefined : "vt-off"}>
                <td>
                  <span className="vt-name">
                    <Tick
                      isSelected={ticked}
                      onChange={(on) =>
                        set({
                          variables: on ? [...chosen, it.variable] : chosen.filter((v) => v !== it.variable),
                        })
                      }
                    >
                      {names[it.variable] ?? it.variable}{" "}
                      {!it.category && <span className="mono wiz-from">{best.column}</span>}
                    </Tick>
                    {test === "corr" && !it.category && g?.corr[best.column] && (
                      <Button
                        className="wiz-link vt-values"
                        aria-expanded={how.has(best.column)}
                        onPress={() => flip(best.column)}
                      >
                        {vt.how}
                      </Button>
                    )}
                    {it.category && (
                      <Button
                        className="wiz-link vt-values"
                        aria-expanded={shown}
                        onPress={() =>
                          setOpen((was) => {
                            const now = new Set(was);
                            if (now.has(it.variable)) now.delete(it.variable);
                            else now.add(it.variable);
                            return now;
                          })
                        }
                      >
                        <Chevron aria-hidden="true" size="0.9em" />
                        {vt.values(passing, it.rows.length)}
                      </Button>
                    )}
                  </span>
                </td>
                {cells(
                  it.category
                    ? passing
                      ? true
                      : it.rows.some((x) => x.passed === false)
                        ? false
                        : null
                    : best.passed,
                  best,
                )}
              </tr>,
              ...(!it.category && how.has(best.column) && g?.corr[best.column]
                ? [
                    <CorrHow
                      key={`${best.column}-how`}
                      d={g.corr[best.column]}
                      names={names}
                      floor={threshold ?? 0.1}
                    />,
                  ]
                : []),
              ...(it.category && shown
                ? it.rows.flatMap((x) => [
                    <tr key={x.column} className={ticked ? "vt-level" : "vt-level vt-off"}>
                      <td>
                        {x.level} <span className="mono wiz-from">{x.column}</span>{" "}
                        {test === "corr" && g?.corr[x.column] && (
                          <Button
                            className="wiz-link vt-values"
                            aria-expanded={how.has(x.column)}
                            onPress={() => flip(x.column)}
                          >
                            {vt.how}
                          </Button>
                        )}
                      </td>
                      {cells(x.passed, x)}
                    </tr>,
                    ...(how.has(x.column) && g?.corr[x.column]
                      ? [
                          <CorrHow
                            key={`${x.column}-how`}
                            d={g.corr[x.column]}
                            names={names}
                            floor={threshold ?? 0.1}
                          />,
                        ]
                      : []),
                  ])
                : []),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

/** OpenAVMKit's pick per model group beside what's ticked, and its weighted scores. */
export function Verdict({
  view,
  setup,
  set,
}: {
  view: VarTestView;
  setup: ModelSetup;
  set: (body: ModelPatch) => void;
}) {
  const r = view.receipt;
  if (!r) return null;
  const tested = r.groups.filter((g) => Object.keys(g.tests).length > 0);
  const chosen = setup.variables.filter((x) => x.chosen).map((x) => x.field);
  const recommended = new Set(tested.flatMap((g) => g.recommended));
  const rows = setup.variables.filter((x) => r.variables.includes(x.field));
  return (
    <div className="cs-step">
      <p className="wiz-lede">{vt.verdictLede}</p>
      <ColumnsNote v={setup} />
      <p>
        {vt.ticked(chosen.length, setup.variables.length)}{" "}
        <Button
          className="wiz-link"
          onPress={() => set({ variables: chosen.filter((v) => recommended.has(v)) })}
        >
          {vt.keepRecommended}
        </Button>
      </p>
      <table className="bi-tbl cs-tbl">
        <thead>
          <tr>
            <th>{vt.variable}</th>
            {tested.map((g) => (
              <th key={g.id} className="cs-n">
                <span className="mg-sw ab-sw" style={{ background: g.color }} />
                {g.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((x) => (
            <tr key={x.field} className={x.chosen ? undefined : "vt-off"}>
              <td>
                <Tick
                  isSelected={x.chosen}
                  onChange={(on) =>
                    set({ variables: on ? [...chosen, x.field] : chosen.filter((v) => v !== x.field) })
                  }
                >
                  {x.name} <span className="mono wiz-from">{x.field}</span>
                </Tick>
              </td>
              {tested.map((g) => (
                <td key={g.id} className="cs-n">
                  <span className="rv-cell">
                    <span className="rv-cell-pill">
                      {g.recommended.includes(x.field) && (
                        <span className="rv-pill rv-ok">✓ {vt.recommended}</span>
                      )}
                    </span>
                    <span>{g.scores[x.field] == null ? "—" : num(g.scores[x.field], 0)}</span>
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** How a correlation score came about: its correlation with price (strength), its clarity (how little it overlaps
 * the others), the score from the two, the variables it overlaps most and, if it was dropped for one, which. */
function CorrHow({
  d,
  names,
  floor,
}: {
  d: CorrDetail | undefined;
  names: Record<string, string>;
  floor: number;
}) {
  if (!d) return null;
  const label = (o: { variable: string; level?: string | null }) =>
    o.level ? vt.level(names[o.variable] ?? o.variable, o.level) : (names[o.variable] ?? o.variable);
  const strength = d.to_price == null ? null : Math.abs(d.to_price);
  return (
    <tr className="vt-how">
      <td colSpan={3}>
        <div className="vt-how-body">
          <span className="vt-how-fig">
            <span className="wiz-from">{vt.howStrength}</span>
            <b>
              {d.to_price == null ? "—" : `${d.to_price >= 0 ? "+" : "−"}${num(Math.abs(d.to_price), 3)}`}
            </b>
            <span className="vt-bar">
              <span className="vt-fill" style={{ width: `${100 * (strength ?? 0)}%` }} />
            </span>
          </span>
          <span className="vt-how-fig">
            <span className="wiz-from">{vt.howClarity}</span>
            <b>{num(d.clarity, 3)}</b>
            <span className="vt-bar">
              <span className="vt-fill" style={{ width: `${100 * Math.max(0, d.clarity ?? 0)}%` }} />
            </span>
          </span>
          <span className="vt-how-fig">
            <span className="wiz-from">{vt.howScore}</span>
            <b>
              {strength == null || d.clarity == null
                ? "—"
                : `${num(strength, 3)} × ${num(d.clarity, 3)}² = ${num(d.score, 3)}`}
            </b>
            <span className="wiz-from">{vt.howFloor(num(floor, 2))}</span>
          </span>
        </div>
        {d.overlaps.length > 0 && (
          <p className="vt-how-line">
            <span className="wiz-from">{vt.howOverlaps}</span>{" "}
            {d.overlaps.map((o) => `${label(o)} ${o.r >= 0 ? "+" : "−"}${num(Math.abs(o.r), 2)}`).join(" · ")}
          </p>
        )}
        {d.dropped_by && (
          <p className="vt-how-line wiz-warn">
            {vt.howDropped(
              label(d.dropped_by),
              num(Math.abs(d.dropped_by.r), 2),
              num(Math.abs(d.dropped_by_price ?? 0), 3),
              num(strength, 3),
            )}{" "}
            {d.near_tie === true
              ? vt.nearTie(label(d.dropped_by))
              : d.near_tie === false
                ? vt.clearWin(label(d.dropped_by))
                : null}
          </p>
        )}
        {d.kept_over.length > 0 && (
          <p className="vt-how-line">
            {vt.keptOver(d.kept_over.map((o) => `${label(o)} (${num(Math.abs(o.r), 2)})`).join(", "))}
          </p>
        )}
      </td>
    </tr>
  );
}

/** Which tests to run (SPEC F9): Represented always; the others as the user picks. */
export function TestPicker({
  setup,
  set,
  disabled,
}: {
  setup: ModelSetup;
  set: (body: ModelPatch) => void;
  disabled: boolean;
}) {
  const chosen = setup.tests;
  return (
    <>
      <h3 className="wiz-group">{vt.pickTitle}</h3>
      <div className="md-engines">
        {["represented", "corr", "p_value", "vif"].map((k) => (
          <div key={k} className="md-engine">
            <Tick
              isSelected={k === "represented" || chosen.includes(k)}
              isDisabled={disabled || k === "represented" || (chosen.includes(k) && chosen.length === 1)}
              onChange={(on) => set({ tests: on ? [...chosen, k] : chosen.filter((x) => x !== k) })}
            >
              <b>{t.values.steps[k as keyof typeof t.values.steps]}</b>
            </Tick>
            <span className="wiz-from">{vt.pick[k]}</span>
          </div>
        ))}
      </div>
    </>
  );
}
