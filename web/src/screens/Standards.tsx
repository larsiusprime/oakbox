/** Check my values › Standards, in three parts: whose (the IAAO's or custom), the standards themselves (every
 * target of each), and which model groups each one judges. */
import { X } from "lucide-react";
import { useState } from "react";
import { Button, Input, Radio, RadioGroup, TextField } from "react-aria-components";
import type { RatioPatch, RatioSetup } from "../api/client";
import { AddButton } from "../components/AddButton";
import { Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { InfoTip } from "../components/Tip";
import { num } from "../lib/format";
import { t } from "../wording";

const s = t.ratio.standards;
type Props = { v: RatioSetup; set: (body: RatioPatch) => void };
type Std = RatioSetup["standards"][number];

/** Part 1: the IAAO's, or custom (from the IAAO's figures, or with none). */
export function WhoseCard({ v, set }: Props) {
  const [start, setStart] = useState<"iaao" | "empty">("iaao");
  return (
    <div className="rv-cards">
      <RadioGroup
        aria-label={s.whose}
        className="cu-choices"
        value={v.source}
        onChange={(x) => set(x === "iaao" ? { source: "iaao" } : { source: "custom", start_from: start })}
      >
        <Radio value="iaao" className="radio cu-choice">
          <span className="radio-dot" aria-hidden="true" />
          <span className="cu-text">
            <b>{s.iaao[0]}</b>
            <span className="cu-sub">{s.iaao[1]}</span>
          </span>
        </Radio>
        <Radio value="custom" className="radio cu-choice">
          <span className="radio-dot" aria-hidden="true" />
          <span className="cu-text">
            <b>{s.custom[0]}</b>
            <span className="cu-sub">{s.custom[1]}</span>
          </span>
        </Radio>
      </RadioGroup>
      <RadioGroup
        aria-label={s.startWith}
        className="rv-choices rv-start"
        value={start}
        onChange={(x) => {
          setStart(x as "iaao" | "empty");
          // Already custom: starting over is asked for here.
          if (v.source === "custom") set({ source: "custom", start_from: x as "iaao" | "empty" });
        }}
      >
        <span className="wiz-from">{s.startWith}</span>
        <Radio value="iaao" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {s.startIaao}
        </Radio>
        <Radio value="empty" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {s.startEmpty}
        </Radio>
      </RadioGroup>
      <p className="wiz-from">{s.source}</p>
    </div>
  );
}

/** A figure in a table cell: saved when it's left. */
function Num({ label, value, onCommit }: { label: string; value: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState<string | null>(null);
  const save = () => {
    const n = Number.parseFloat(text ?? "");
    if (text !== null && Number.isFinite(n) && n !== value) onCommit(n);
    setText(null);
  };
  return (
    <TextField
      aria-label={label}
      value={text ?? String(value)}
      onChange={setText}
      onBlur={save}
      className="rv-numcell"
    >
      <Input
        className="input"
        inputMode="decimal"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

function Name({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [text, setText] = useState<string | null>(null);
  const save = () => {
    const next = text?.trim();
    if (next && next !== value) onCommit(next);
    setText(null);
  };
  return (
    <TextField
      aria-label={s.name}
      value={text ?? value}
      onChange={setText}
      onBlur={save}
      className="rv-namecell"
    >
      <Input
        className="input"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

/** Part 2: the standards, a row each, every target changeable; add, remove, back to the IAAO's. */
export function StandardsTable({ v, set }: Props) {
  const all = v.standards;
  const put = (i: number, patch: Partial<Std>) =>
    set({ standards: all.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const add = () => {
    const n = all.length + 1;
    const id = `std${Date.now().toString(36)}`;
    set({
      standards: [
        ...all,
        {
          id,
          name: s.newName({ n }),
          level_low: 0.9,
          level_high: 1.1,
          cod_low: 5,
          cod_high: 15,
          prb_good: 0.05,
          prb_bad: 0.1,
          vei: 10,
          min_sales: 5,
          groups: all.some((x) => x.groups?.length) ? [] : null,
        },
      ],
    });
  };
  const head = (label: string, tip: string) => (
    <th>
      <InfoTip label={label} text={tip} />
    </th>
  );
  return (
    <div className="rv-cards">
      {all.length === 0 ? (
        <p className="wiz-from">{s.none}</p>
      ) : (
        <table className="tbl rv-standards">
          <thead>
            <tr>
              <th>{s.standard}</th>
              {head(s.level, s.levelWhy)}
              {head(s.cod, s.codWhy)}
              {head(s.prbGood, s.prbWhy)}
              {head(s.prbBad, s.prbWhy)}
              {head(s.vei, s.veiWhy)}
              {head(s.minSales, s.minSalesWhy)}
              <th />
            </tr>
          </thead>
          <tbody>
            {all.map((x, i) => (
              <tr key={x.id}>
                <td>
                  <Name value={x.name} onCommit={(name) => put(i, { name })} />
                </td>
                <td>
                  <span className="rv-pair">
                    <Num
                      label={`${x.name}: ${s.level}, ${s.from}`}
                      value={x.level_low}
                      onCommit={(n) => put(i, { level_low: n })}
                    />
                    –
                    <Num
                      label={`${x.name}: ${s.level}, ${s.to}`}
                      value={x.level_high}
                      onCommit={(n) => put(i, { level_high: n })}
                    />
                  </span>
                </td>
                <td>
                  <span className="rv-pair">
                    <Num
                      label={`${x.name}: ${s.cod}, ${s.from}`}
                      value={x.cod_low}
                      onCommit={(n) => put(i, { cod_low: n })}
                    />
                    –
                    <Num
                      label={`${x.name}: ${s.cod}, ${s.to}`}
                      value={x.cod_high}
                      onCommit={(n) => put(i, { cod_high: n })}
                    />
                  </span>
                </td>
                <td>
                  <span className="rv-pair">
                    ±
                    <Num
                      label={`${x.name}: ${s.prbGood}`}
                      value={x.prb_good}
                      onCommit={(n) => put(i, { prb_good: n })}
                    />
                  </span>
                </td>
                <td>
                  <span className="rv-pair">
                    ±
                    <Num
                      label={`${x.name}: ${s.prbBad}`}
                      value={x.prb_bad}
                      onCommit={(n) => put(i, { prb_bad: n })}
                    />
                  </span>
                </td>
                <td>
                  <span className="rv-pair">
                    ±<Num label={`${x.name}: ${s.vei}`} value={x.vei} onCommit={(n) => put(i, { vei: n })} />%
                  </span>
                </td>
                <td>
                  <Num
                    label={`${x.name}: ${s.minSales}`}
                    value={x.min_sales}
                    onCommit={(n) => put(i, { min_sales: Math.max(1, Math.round(n)) })}
                  />
                </td>
                <td>
                  <Button
                    className="wiz-link vs-remove"
                    onPress={() => set({ standards: all.filter((_, j) => j !== i) })}
                  >
                    <X aria-hidden="true" size="0.9em" />
                    {s.remove}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="cs-row add-row">
        <AddButton onPress={add}>{s.add}</AddButton>
        {!v.iaao && (
          <Button className="wiz-link" onPress={() => set({ reset_standards: true })}>
            {s.reset}
          </Button>
        )}
      </p>
      <p className="wiz-from">{s.prdNote}</p>
      <Tick isSelected={v.trim} onChange={(on) => set({ trim: on })}>
        {s.trim}
      </Tick>
    </div>
  );
}

/** Part 3: which model groups each standard judges; a group in one at most; the rest shown, not judged. */
export function AssignTable({ v, set }: Props) {
  const all = v.standards;
  const groups = v.groups;
  const sales = new Map(groups.map((g) => [g.id, g.sales]));
  const pick = (i: number, chosen: string[]) =>
    // Every standard's groups written down, as they are now: from here on they're chosen, not proposed.
    set({
      standards: all.map((x, j) =>
        j === i
          ? { ...x, groups: chosen }
          : { ...x, groups: (x.groups ?? []).filter((g) => !chosen.includes(g)) },
      ),
    });
  const judged = new Set(all.flatMap((x) => x.groups ?? []));
  const left = groups.filter((g) => !judged.has(g.id));
  return (
    <div className="rv-cards">
      {all.length === 0 ? (
        <p className="wiz-from">{s.noneToAssign}</p>
      ) : (
        <table className="tbl rv-assign">
          <thead>
            <tr>
              <th>{s.standard}</th>
              <th>{s.groups}</th>
              <th className="cs-n">{s.salesCol}</th>
            </tr>
          </thead>
          <tbody>
            {all.map((x, i) => {
              const mine = x.groups ?? [];
              const n = mine.reduce((a, g) => a + (sales.get(g) ?? 0), 0);
              return (
                <tr key={x.id}>
                  <td>
                    <b>{x.name}</b>
                  </td>
                  <td>
                    <MultiPick
                      label={`${s.groups}: ${x.name}`}
                      placeholder={s.chooseGroups}
                      values={groups.map((g) => ({ value: g.id, label: g.name }))}
                      chosen={mine}
                      onChange={(chosen) => pick(i, chosen)}
                    />
                  </td>
                  <td className="cs-n">{mine.length ? num(n) : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {left.length > 0 && (
        <p className="wiz-from">{s.notJudged({ names: left.map((g) => g.name).join(", ") })}</p>
      )}
      {groups.some((g) => g.proposed) && all.some((x) => x.groups?.length) && (
        <p className="wiz-from">{s.proposedNote}</p>
      )}
    </div>
  );
}
