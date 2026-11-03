/** Model groups' editor of one group: its name and its conditions, each a field, a test and the values it takes. */
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { Button, Input, TextField } from "react-aria-components";
import {
  api,
  type Condition,
  type GroupField,
  type GroupsPreview,
  type ModelGroup,
  unwrap,
} from "../api/client";
import { AddButton } from "../components/AddButton";
import { Choice } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { moneyShort } from "../lib/format";
import { t } from "../strings";
import type { Move } from "./ModelGroups";

const g = t.groups;

type Op = Condition["op"];
const LISTS: Op[] = ["isin", "notin"];
const NO_VALUE: Op[] = ["isempty", "notempty"];
const NUMBER_OPS: Op[] = [">", "<", ">=", "<=", "==", "!=", "isempty", "notempty"];
const CATEGORY_OPS: Op[] = ["isin", "notin", "contains", "isempty", "notempty"];

export function useValues(projectId: string, field: string, enabled = true) {
  return useQuery({
    queryKey: ["group-values", projectId, field],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/groups/values/{field}", {
          params: { path: { project_id: projectId, field } },
        }),
      ),
    enabled: enabled && !!field,
    staleTime: 60_000,
  });
}

export function GroupEditor({
  projectId,
  currency,
  group,
  order,
  fields,
  colors,
  stats,
  preview,
  name,
  onChange,
  onDelete,
  onShow,
  moved,
}: {
  projectId: string;
  currency: string;
  group: ModelGroup;
  order: number;
  fields: GroupField[];
  colors: string[];
  stats: GroupsPreview["stats"][number] | undefined;
  preview: GroupsPreview | undefined;
  name: (id: string) => string;
  onChange: (patch: Partial<ModelGroup>) => void;
  onDelete: () => void;
  onShow: (indexes: number[]) => void;
  moved: (m: Move) => number[];
}) {
  const rule = group.rule;
  const setConditions = (conditions: Condition[]) => onChange({ rule: { ...rule, conditions } });
  const set = (i: number, patch: Partial<Condition>) =>
    setConditions(rule.conditions.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const kind = (f: string) => fields.find((x) => x.name === f)?.kind ?? "category";
  // Fields by name ("Land use"), so a condition fits on one line.
  const options = fields.map((f) => [f.name, f.label] as const);
  const moves = preview?.moves.filter((m) => m.to_id === group.id || m.from_id === group.id) ?? [];
  return (
    <div className="mg-editor">
      <div className="mg-ed-head">
        <span className="mg-sw big" style={{ background: group.color }} />
        <TextField
          className="mg-name"
          value={group.name}
          onChange={(name) => onChange({ name })}
          aria-label={g.name}
        >
          <Input className="input mg-name-input" />
        </TextField>
        <span className="mg-nth">{g.nth(order)}</span>
      </div>
      <div className="mg-colours" role="radiogroup" aria-label={g.colour}>
        {colors.map((c) => (
          <Button
            key={c}
            className={`mg-colour${c === group.color ? " on" : ""}`}
            style={{ background: c }}
            aria-label={c}
            onPress={() => onChange({ color: c })}
          />
        ))}
      </div>
      {stats && (
        <div className="mg-stats">
          <div>
            <b className="mg-stat-n">{stats.parcels.toLocaleString()}</b>
            <span className="mg-stat-l">{g.statParcels(stats.vacant)}</span>
          </div>
          <div>
            <b className="mg-stat-n">{stats.sales.toLocaleString()}</b>
            <span className="mg-stat-l">{g.statSales}</span>
          </div>
          <div>
            <b className="mg-stat-n">{stats.vacant_sales.toLocaleString()}</b>
            <span className="mg-stat-l">{g.statVacant}</span>
          </div>
          <div>
            <b className="mg-stat-n">{moneyShort(stats.median_price, currency)}</b>
            <span className="mg-stat-l">{g.statMedian}</span>
          </div>
        </div>
      )}
      <div className="mg-card">
        <div className="mg-join">
          <span>{g.joinsIf}</span>
          <Choice
            label={g.joinsIf}
            hideLabel
            value={rule.join}
            options={[
              ["any", g.any],
              ["all", g.all],
            ]}
            onChange={(join) => onChange({ rule: { ...rule, join } })}
          />
        </div>
        <ol className="mg-conds">
          {rule.conditions.map((c, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: conditions have no id; their place is what they are
            <li key={i} className="mg-cond">
              <div className="rl-head">
                <Choice
                  label={g.field}
                  hideLabel
                  value={c.column}
                  options={options}
                  onChange={(column) =>
                    set(i, { column, op: kind(column) === "number" ? ">=" : "isin", values: [] })
                  }
                />
                <Choice
                  label={g.op}
                  hideLabel
                  value={c.op}
                  options={(kind(c.column) === "number" ? NUMBER_OPS : CATEGORY_OPS).map(
                    (op) => [op, t.wizard.rule.ops[op] ?? op] as const,
                  )}
                  onChange={(op) =>
                    set(i, { op, values: LISTS.includes(op) === LISTS.includes(c.op) ? c.values : [] })
                  }
                />
                {LISTS.includes(c.op) ? (
                  <CondValues
                    projectId={projectId}
                    field={c.column}
                    chosen={c.values}
                    onChange={(values) => set(i, { values })}
                  />
                ) : NO_VALUE.includes(c.op) ? null : (
                  <TextField
                    aria-label={t.wizard.rule.value}
                    value={c.values[0] ?? ""}
                    onChange={(x) => set(i, { values: x ? [x] : [] })}
                    className="rl-mini"
                  >
                    <Input className="input rl-input" />
                  </TextField>
                )}
                <Button
                  className="rc-x"
                  aria-label={g.removeCondition}
                  onPress={() => setConditions(rule.conditions.filter((_, j) => j !== i))}
                >
                  <X size="0.9em" />
                </Button>
              </div>
            </li>
          ))}
        </ol>
        <div className="mg-card-foot">
          <AddButton
            onPress={() =>
              setConditions([
                ...rule.conditions,
                { column: rule.conditions.at(-1)?.column ?? fields[0]?.name ?? "", op: "isin", values: [] },
              ])
            }
          >
            {g.addCondition}
          </AddButton>
          <span className="mg-help">{g.counts}</span>
        </div>
      </div>
      {moves.length > 0 && (
        <div className="mg-live">
          <b className="mg-live-t">{g.live}</b>
          {moves.map((m) => (
            <span key={`${m.from_id}>${m.to_id}`}>
              {m.to_id === group.id
                ? g.moveIn(m.parcels, name(m.from_id), m.sold)
                : g.moveOut(m.parcels, name(m.to_id), m.sold)}{" "}
              <Button className="wiz-link" onPress={() => onShow(moved(m))}>
                {g.showMoves}
              </Button>
            </span>
          ))}
        </div>
      )}
      {stats && stats.checks.length > 0 && (
        <div className="mg-card">
          <h4 className="mg-card-h">{g.checks}</h4>
          <ul className="mg-checks">
            {stats.checks.map((c) => (
              <li key={c.text} className={`mg-check ${c.level}`}>
                {c.level === "ok" ? "✓ " : c.level === "warn" ? "▲ " : "● "}
                {c.text}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mg-ed-foot">
        <Button className="wiz-link" onPress={onDelete}>
          {g.deleteGroup}
        </Button>
      </div>
    </div>
  );
}

function CondValues({
  projectId,
  field,
  chosen,
  onChange,
}: {
  projectId: string;
  field: string;
  chosen: string[];
  onChange: (v: string[]) => void;
}) {
  const vals = useValues(projectId, field);
  const rows = vals.data?.rows ?? [];
  return (
    <MultiPick
      label={t.wizard.rule.value}
      values={rows.map((r) => ({ value: r.value, count: r.parcels }))}
      more={vals.data?.more ?? 0}
      chosen={chosen}
      onChange={onChange}
      countNoun={g.countParcels}
    />
  );
}
