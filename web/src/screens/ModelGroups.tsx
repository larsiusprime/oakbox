import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Dialog, Heading, Input, Modal, ModalOverlay, TextField } from "react-aria-components";
import {
  api,
  type Condition,
  type GroupField,
  type GroupsPreview,
  type GroupsView,
  type ModelGroup,
  type ParcelInspect,
  unwrap,
} from "../api/client";
import { Choice } from "../components/Form";
import { Seg } from "../components/Seg";
import { t } from "../strings";
import { useSettled, ValuePicker } from "./FieldRules";

const g = t.groups;
type Op = Condition["op"];
const LISTS: Op[] = ["isin", "notin"];
const NO_VALUE: Op[] = ["isempty", "notempty"];
const NUMBER_OPS: Op[] = [">", "<", ">=", "<=", "==", "!=", "isempty", "notempty"];
const CATEGORY_OPS: Op[] = ["isin", "notin", "contains", "isempty", "notempty"];
type MapMode = "docked" | "full" | "hidden";
type ColourBy = "group" | "changes";

function useGroups(projectId: string) {
  return useQuery({
    queryKey: ["groups", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/groups", { params: { path: { project_id: projectId } } }),
      ),
  });
}

/** Step 2, Model groups (SPEC §3.5): choose how to start, then the builder. */
export function ModelGroupsTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const state = useGroups(projectId);
  const start = useMutation({
    mutationFn: async (how: "scratch" | "suggested") =>
      unwrap(
        await api.POST("/api/projects/{project_id}/groups/start", {
          params: { path: { project_id: projectId } },
          body: { how },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(["groups", projectId], data),
  });
  const v = state.data;
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  if (!v.ready) return <p className="bi-lede mg-pad">{g.notReady}</p>;
  if (!v.start)
    return (
      <div className="mg-start">
        <div className="bi-kicker">{g.kicker}</div>
        <h2 className="bi-title">{g.title}</h2>
        <p className="bi-lede">{g.lede}</p>
        <h3 className="mg-start-q">{g.startTitle}</h3>
        <div className="mg-start-cards">
          <Button
            className="mg-start-card"
            isDisabled={!v.can_suggest || start.isPending}
            onPress={() => start.mutate("suggested")}
          >
            <b>{g.suggested}</b>
            <span>{v.can_suggest ? g.suggestedHelp : g.noSuggest}</span>
          </Button>
          <Button
            className="mg-start-card"
            isDisabled={start.isPending}
            onPress={() => start.mutate("scratch")}
          >
            <b>{g.scratch}</b>
            <span>{g.scratchHelp}</span>
          </Button>
        </div>
        {start.error && (
          <p className="error" role="alert">
            {start.error.message}
          </p>
        )}
      </div>
    );
  return <Builder projectId={projectId} view={v} />;
}

function same(a: ModelGroup[], b: ModelGroup[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function newId(name: string, groups: ModelGroup[]): string {
  const base =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "") || "group";
  let id = base;
  for (let n = 2; groups.some((x) => x.id === id); n++) id = `${base}_${n}`;
  return id;
}

function money(v: number | null | undefined): string {
  if (v == null) return "—";
  return v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1000).toLocaleString()}k`;
}

function Builder({ projectId, view }: { projectId: string; view: GroupsView }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ModelGroup[]>(view.groups);
  const [selected, setSelected] = useState<string | null>(view.groups[0]?.id ?? null);
  const [mapMode, setMapMode] = useState<MapMode>("docked");
  const [colourBy, setColourBy] = useState<ColourBy>("group");
  const [picked, setPicked] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number[] | null>(null);
  const [fromField, setFromField] = useState(false);
  const dirty = !same(draft, view.groups);

  const asked = useSettled(draft, 200);
  const preview = useQuery({
    queryKey: ["groups-preview", projectId, asked],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/groups/preview", {
          params: { path: { project_id: projectId } },
          body: { groups: asked },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const save = useMutation({
    mutationFn: async (groups: ModelGroup[]) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/groups", {
          params: { path: { project_id: projectId } },
          body: { groups },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["groups", projectId], data);
      setDraft(data.groups);
    },
  });
  const p = preview.data;
  // The preview's indexes are into the groups it was asked about (asked), and the saved groups.
  const moved = (m: Move): number[] => {
    if (!p) return [];
    const now = asked.map((x) => x.id);
    const before = view.groups.map((x) => x.id);
    return p.assign.flatMap((a, i) =>
      (now[a] ?? "") === m.to_id && (before[p.saved[i] ?? -1] ?? "") === m.from_id ? [i] : [],
    );
  };
  const colours = useMemo(() => asked.map((x) => x.color), [asked]);
  const statsFor = (id: string) => p?.stats.find((s) => s.id === id);
  const group = draft.find((x) => x.id === selected) ?? null;
  const name = (id: string) =>
    id === ""
      ? g.unassigned
      : (draft.find((x) => x.id === id)?.name ?? view.groups.find((x) => x.id === id)?.name ?? id);

  const update = (id: string, patch: Partial<ModelGroup>) =>
    setDraft(draft.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  const move = (i: number, by: number) => {
    const next = [...draft];
    const [x] = next.splice(i, 1);
    if (x) next.splice(i + by, 0, x);
    setDraft(next);
  };
  const add = () => {
    const nm = g.newName(draft.length + 1);
    const used = new Set(draft.map((x) => x.color));
    const color =
      view.colors.find((c) => !used.has(c)) ?? view.colors[draft.length % view.colors.length] ?? "#888";
    const first = view.fields[0]?.name ?? "";
    const x: ModelGroup = {
      id: newId(nm, draft),
      name: nm,
      color,
      rule: { join: "any", conditions: [{ column: first, op: "isin", values: [] }] },
      numeric: [],
    };
    setDraft([...draft, x]);
    setSelected(x.id);
  };

  const mapShown = mapMode !== "hidden";
  return (
    <div className={`mg mg-${mapMode}`}>
      <div className="mg-list">
        <h3 className="mg-h">{g.listTitle}</h3>
        <ol className="mg-items">
          {draft.map((x, i) => (
            <GroupItem
              key={x.id}
              name={x.name}
              color={x.color}
              stats={statsFor(x.id)}
              delta={delta(p, x.id)}
              isSelected={x.id === selected}
              onSelect={() => {
                setSelected(x.id);
                if (mapMode === "full") setMapMode("docked");
              }}
              onUp={i > 0 ? () => move(i, -1) : undefined}
              onDown={i < draft.length - 1 ? () => move(i, 1) : undefined}
            />
          ))}
        </ol>
        <div className="mg-sep" />
        <GroupItem
          name={g.unassigned}
          color={view.unassigned_color}
          stats={statsFor("")}
          delta={delta(p, "")}
          isSelected={false}
          onSelect={() => {
            const n = p?.assign.flatMap((a, i) => (a === -1 ? [i] : [])) ?? [];
            setHighlight(n);
          }}
        />
        <div className="mg-adds">
          <Button className="button" onPress={add}>
            {g.addGroup}
          </Button>
          <Button className="button" onPress={() => setFromField(true)}>
            {g.fromField}
          </Button>
        </div>
        <p className="mg-help">{g.orderHelp}</p>
        <div className="mg-save">
          <Button className="button" isDisabled={!dirty} onPress={() => setDraft(view.groups)}>
            {g.undo}
          </Button>
          <Button
            className="button button-primary"
            isDisabled={!dirty || save.isPending}
            onPress={() => save.mutate(draft)}
          >
            {g.save}
          </Button>
          {!dirty && view.groups.length > 0 && <span className="mg-saved">{g.saved}</span>}
        </div>
        {save.error && (
          <p className="error" role="alert">
            {save.error.message}
          </p>
        )}
      </div>

      {mapMode !== "full" && (
        <div className="mg-ed">
          {group ? (
            <GroupEditor
              key={group.id}
              projectId={projectId}
              group={group}
              order={draft.indexOf(group) + 1}
              fields={view.fields}
              colors={view.colors}
              stats={statsFor(group.id)}
              preview={p}
              name={name}
              onChange={(patch) => update(group.id, patch)}
              onDelete={() => {
                setDraft(draft.filter((x) => x.id !== group.id));
                setSelected(null);
              }}
              onShow={(n) => {
                setHighlight(n);
                if (!mapShown) setMapMode("docked");
              }}
              moved={moved}
            />
          ) : (
            <p className="bi-lede">{g.pickGroup}</p>
          )}
          {!mapShown && (
            <Button className="button mg-showmap" onPress={() => setMapMode("docked")}>
              {g.showMap}
            </Button>
          )}
        </div>
      )}

      {mapShown && (
        <div className="mg-map">
          <div className="mg-bar">
            <b>{g.map}</b>
            <Seg
              value={colourBy}
              options={[
                ["group", g.byGroup],
                ["changes", g.byChanges],
              ]}
              onChange={setColourBy}
            />
            {highlight && (
              <span className="mg-hl">
                {g.highlighted(highlight.length)}{" "}
                <Button className="wiz-link" onPress={() => setHighlight(null)}>
                  {g.clearHighlight}
                </Button>
              </span>
            )}
            <span className="mg-grow" />
            <span className="mg-hint">{g.clickHint}</span>
            <Seg
              value={mapMode}
              options={[
                ["docked", g.docked],
                ["full", g.full],
              ]}
              onChange={setMapMode}
            />
            <Button className="mg-x" aria-label={g.hide} onPress={() => setMapMode("hidden")}>
              <X size="0.9em" />
            </Button>
          </div>
          <ParcelMap
            projectId={projectId}
            preview={p}
            colours={colours}
            unassigned={view.unassigned_color}
            colourBy={colourBy}
            highlight={highlight}
            picked={picked}
            mode={mapMode}
            onPick={setPicked}
          />
          {picked != null && (
            <Inspector
              projectId={projectId}
              groups={asked}
              index={picked}
              name={name}
              colour={(id) =>
                id === "" ? view.unassigned_color : (asked.find((x) => x.id === id)?.color ?? "#888")
              }
              onShow={(n) => setHighlight(n)}
              onClose={() => setPicked(null)}
            />
          )}
          <Legend
            items={
              colourBy === "group"
                ? [
                    ...asked.map((x) => [x.color, x.name] as const),
                    [view.unassigned_color, g.unassigned] as const,
                  ]
                : [
                    ...asked.map((x) => [x.color, `${g.movesTo} ${x.name}`] as const),
                    [CHANGE_GREY, g.noChanges] as const,
                  ]
            }
          />
        </div>
      )}
      {fromField && (
        <FromField
          projectId={projectId}
          fields={view.fields}
          groups={draft}
          colors={view.colors}
          close={() => setFromField(false)}
          apply={(groups) => {
            setDraft(groups);
            setFromField(false);
            setSelected(groups[0]?.id ?? null);
          }}
        />
      )}
    </div>
  );
}

const CHANGE_GREY = "#d9dcd4";
type Move = GroupsPreview["moves"][number];

/** Parcels in and out of a group since the saved groups. */
function delta(p: GroupsPreview | undefined, id: string): number {
  if (!p) return 0;
  return p.moves.reduce(
    (n: number, m: Move) => n + (m.to_id === id ? m.parcels : 0) - (m.from_id === id ? m.parcels : 0),
    0,
  );
}

function Legend({ items }: { items: readonly (readonly [string, string])[] }) {
  return (
    <div className="mg-legend">
      {items.map(([c, label]) => (
        <span key={label}>
          <i style={{ background: c }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function GroupItem({
  name,
  color,
  stats,
  delta,
  isSelected,
  onSelect,
  onUp,
  onDown,
}: {
  name: string;
  color: string;
  stats: GroupsPreview["stats"][number] | undefined;
  delta: number;
  isSelected: boolean;
  onSelect: () => void;
  onUp?: (() => void) | undefined;
  onDown?: (() => void) | undefined;
}) {
  // In the list, only what needs a look; the editor has every check.
  const worst = stats?.checks.find((c) => c.level === "bad") ?? stats?.checks.find((c) => c.level === "warn");
  return (
    <li className={`mg-item${isSelected ? " sel" : ""}`}>
      <Button className="mg-item-main" onPress={onSelect}>
        <span className="mg-sw" style={{ background: color }} />
        <span className="mg-nm">
          {name}
          {delta !== 0 && (
            <span className={`mg-delta ${delta > 0 ? "up" : "dn"}`}>
              {delta > 0 ? `+${delta}` : `−${-delta}`}
            </span>
          )}
        </span>
        {stats && (
          <span className="mg-ct">
            {g.parcels(stats.parcels)} · {g.sales(stats.sales, stats.vacant_sales)}
          </span>
        )}
        {worst && <span className={`mg-check ${worst.level}`}>{worst.text}</span>}
      </Button>
      {(onUp || onDown) && (
        <span className="mg-order">
          <Button className="mg-arrow" aria-label={g.up(name)} isDisabled={!onUp} onPress={() => onUp?.()}>
            <ArrowUp size="0.8em" />
          </Button>
          <Button
            className="mg-arrow"
            aria-label={g.down(name)}
            isDisabled={!onDown}
            onPress={() => onDown?.()}
          >
            <ArrowDown size="0.8em" />
          </Button>
        </span>
      )}
    </li>
  );
}

function useValues(projectId: string, field: string, enabled = true) {
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

function GroupEditor({
  projectId,
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
  const options = fields.map(
    (f) => [f.name, f.label === f.name ? f.name : `${f.label} (${f.name})`] as const,
  );
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
            <b className="mg-stat-n">{money(stats.median_price)}</b>
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
                <Button
                  className="rc-x"
                  aria-label={g.removeCondition}
                  onPress={() => setConditions(rule.conditions.filter((_, j) => j !== i))}
                >
                  <X size="0.9em" />
                </Button>
              </div>
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
            </li>
          ))}
        </ol>
        <div className="mg-card-foot">
          <Button
            className="button rc-add"
            onPress={() =>
              setConditions([
                ...rule.conditions,
                { column: rule.conditions.at(-1)?.column ?? fields[0]?.name ?? "", op: "isin", values: [] },
              ])
            }
          >
            {g.addCondition}
          </Button>
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
    <ValuePicker
      values={rows.map((r) => ({ value: r.value, count: r.parcels }))}
      more={vals.data?.more ?? 0}
      chosen={chosen}
      onChange={onChange}
    />
  );
}

/** The parcel shapes on OpenStreetMap (when online), coloured by group or by what moved. */
function ParcelMap({
  projectId,
  preview,
  colours,
  unassigned,
  colourBy,
  highlight,
  picked,
  mode,
  onPick,
}: {
  projectId: string;
  preview: GroupsPreview | undefined;
  colours: string[];
  unassigned: string;
  colourBy: ColourBy;
  highlight: number[] | null;
  picked: number | null;
  mode: MapMode;
  onPick: (i: number) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.GeoJSON | null>(null);
  const outline = useRef<L.GeoJSON | null>(null);
  const shapes = useQuery({
    queryKey: ["group-shapes", projectId],
    queryFn: async () => {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/groups/shapes`);
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as GeoJSON.FeatureCollection;
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
  const style = useRef<(i: number) => L.PathOptions>(() => ({}));
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    if (!el.current || !shapes.data) return;
    const m = L.map(el.current, { preferCanvas: true, zoomSnap: 0.25 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(m);
    const renderer = L.canvas({ padding: 0.3 });
    const gj = L.geoJSON(shapes.data, {
      renderer,
      style: (f) => style.current(Number(f?.id ?? -1)),
      onEachFeature: (f, lyr) => lyr.on("click", () => pick.current(Number(f.id))),
    } as L.GeoJSONOptions).addTo(m);
    layer.current = gj;
    const b = gj.getBounds();
    if (b.isValid()) m.fitBounds(b, { padding: [8, 8] });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      layer.current = null;
      outline.current = null;
    };
  }, [shapes.data]);

  // Recolour without redrawing the shapes (and once they're drawn).
  // biome-ignore lint/correctness/useExhaustiveDependencies: shapes.data: the layer is new when the shapes are
  useEffect(() => {
    const assign = preview?.assign;
    const saved = preview?.saved;
    const hl = highlight ? new Set(highlight) : null;
    style.current = (i: number) => {
      const a = assign?.[i] ?? -1;
      let fill = a >= 0 ? (colours[a] ?? unassigned) : unassigned;
      if (colourBy === "changes") fill = a !== (saved?.[i] ?? -1) ? fill : CHANGE_GREY;
      const dim = hl && !hl.has(i);
      return {
        fillColor: fill,
        fillOpacity: dim ? 0.18 : 0.72,
        color: hl?.has(i) ? "#111" : "#ffffff",
        weight: hl?.has(i) ? 1.4 : 0.4,
        opacity: dim ? 0.3 : 0.9,
      };
    };
    layer.current?.setStyle((f) => style.current(Number(f?.id ?? -1)));
  }, [preview, colours, unassigned, colourBy, highlight, shapes.data]);

  // The picked parcel, outlined on top.
  useEffect(() => {
    const m = map.current;
    outline.current?.remove();
    outline.current = null;
    if (!m || picked == null || !shapes.data) return;
    const f = shapes.data.features[picked];
    if (!f?.geometry) return;
    outline.current = L.geoJSON(f, {
      style: { color: "#000", weight: 3, fill: false },
      interactive: false,
    }).addTo(m);
  }, [picked, shapes.data]);

  useEffect(() => {
    void mode;
    const id = setTimeout(() => map.current?.invalidateSize(), 50);
    return () => clearTimeout(id);
  }, [mode]);

  return (
    <div className="mg-map-body">
      <div ref={el} className="mg-leaflet" />
      {!shapes.data && <p className="mg-map-msg">{shapes.error?.message ?? g.loadingMap}</p>}
    </div>
  );
}

function Inspector({
  projectId,
  groups,
  index,
  name,
  colour,
  onShow,
  onClose,
}: {
  projectId: string;
  groups: ModelGroup[];
  index: number;
  name: (id: string) => string;
  colour: (id: string) => string;
  onShow: (n: number[]) => void;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["group-inspect", projectId, groups, index],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/groups/inspect", {
          params: { path: { project_id: projectId } },
          body: { groups, index },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v: ParcelInspect | undefined = q.data;
  return (
    <section className="mg-pop" aria-label={v ? g.parcel(v.key) : g.parcel("")}>
      <div className="mg-pop-head">
        <b className="mg-pop-title">{v ? g.parcel(v.key) : "…"}</b>
        {v && (
          <span className="mg-tag" style={{ background: colour(v.group) }}>
            {name(v.group)}
          </span>
        )}
        <Button className="rc-x" aria-label={g.close} onPress={onClose}>
          <X size="0.9em" />
        </Button>
      </div>
      {q.error && <p className="error">{q.error.message}</p>}
      {v && (
        <>
          <table className="mg-pop-tbl">
            <tbody>
              {v.fields.map((f) => (
                <tr key={f.label}>
                  <td className="mg-pop-k">{f.label}</td>
                  <td className="mg-pop-v">{f.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <b className="mg-pop-sub">{v.group ? g.whyIn(name(v.group)) : g.whyNone}</b>
          <ol className="mg-why">
            {v.why.map((w) => (
              <li key={w.group} className={w.met ? (w.group === v.group ? "yes" : "also") : "no"}>
                <span aria-hidden="true">{w.met ? "✓" : "✗"}</span>
                <span>
                  {w.order} {name(w.group)}: {w.text}
                  {w.met && w.group !== v.group ? ` · ${g.alsoMeets}` : ""}
                </span>
              </li>
            ))}
          </ol>
          <b className="mg-pop-sub">{g.salesTitle}</b>
          {v.sales.length === 0 ? (
            <span className="mg-dim">{g.noSales}</span>
          ) : (
            <ul className="mg-pop-sales">
              {v.sales.map((s) => (
                <li key={`${s.date}${s.price}`}>
                  {s.date} · {s.price != null ? `$${Math.round(s.price).toLocaleString()}` : "—"}
                  {s.vacant ? ` · ${g.vacantSale}` : ""}
                </li>
              ))}
            </ul>
          )}
          {v.like_text && v.like.length > 1 && (
            <div className="mg-live">
              <span>{g.like(v.like.length, v.like_sold, v.like_text)}</span>
              <Button className="wiz-link" onPress={() => onShow(v.like)}>
                {g.showLike}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

const NONE = "__none";
const NEW = "__new";

/** Send each value of one field to a group: each group gets (or has replaced) its condition on that field. */
function FromField({
  projectId,
  fields,
  groups,
  colors,
  close,
  apply,
}: {
  projectId: string;
  fields: GroupField[];
  groups: ModelGroup[];
  colors: string[];
  close: () => void;
  apply: (groups: ModelGroup[]) => void;
}) {
  const cats = fields.filter((f) => f.kind === "category");
  const [field, setField] = useState(cats[0]?.name ?? "");
  const [list, setList] = useState<ModelGroup[]>(groups);
  const [sent, setSent] = useState<Record<string, string>>({});
  const vals = useValues(projectId, field);
  // What the groups already say about this field.
  useEffect(() => {
    const out: Record<string, string> = {};
    for (const x of groups)
      for (const c of x.rule.conditions)
        if (c.column === field && c.op === "isin") for (const v of c.values) out[v] = out[v] ?? x.id;
    setSent(out);
  }, [field, groups]);
  const addGroup = (value: string) => {
    const nm = value || g.newName(list.length + 1);
    const used = new Set(list.map((x) => x.color));
    const x: ModelGroup = {
      id: newId(nm, list),
      name: nm,
      color: colors.find((c) => !used.has(c)) ?? colors[list.length % colors.length] ?? "#888",
      rule: { join: "any", conditions: [] },
      numeric: [],
    };
    setList([...list, x]);
    return x.id;
  };
  const done = () => {
    const out = list.map((x) => {
      const values = Object.entries(sent)
        .filter(([, id]) => id === x.id)
        .map(([v]) => v);
      const others = x.rule.conditions.filter((c) => !(c.column === field && c.op === "isin"));
      const conditions = values.length ? [...others, { column: field, op: "isin" as const, values }] : others;
      return { ...x, rule: { ...x.rule, conditions } };
    });
    apply(out.filter((x) => x.rule.conditions.length > 0 || groups.some((y) => y.id === x.id)));
  };
  const groupOptions = [
    [NONE, g.ffNone] as const,
    ...list.map((x) => [x.id, x.name] as const),
    [NEW, g.ffNew] as const,
  ];
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal mg-ff">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {g.ffTitle}
          </Heading>
          <p className="rc-sub">{g.ffLede}</p>
          <Choice
            label={g.ffField}
            value={field}
            options={cats.map((f) => [f.name, `${f.label} · ${f.distinct.toLocaleString()}`] as const)}
            onChange={setField}
          />
          <div className="mg-ff-scroll">
            <table className="rc-tbl mg-ff-tbl">
              <thead>
                <tr>
                  <th className="rc-th">{g.ffValue}</th>
                  <th className="rc-th mg-num">{g.ffParcels}</th>
                  <th className="rc-th mg-num">{g.ffVacant}</th>
                  <th className="rc-th mg-num">{g.ffSales}</th>
                  <th className="rc-th">{g.ffGroup}</th>
                </tr>
              </thead>
              <tbody>
                {(vals.data?.rows ?? []).map((r) => (
                  <tr key={r.value}>
                    <td className="rc-td mono">{r.value || g.blank}</td>
                    <td className="rc-td mg-num">{r.parcels.toLocaleString()}</td>
                    <td className="rc-td mg-num">{r.vacant.toLocaleString()}</td>
                    <td className="rc-td mg-num">{r.sales.toLocaleString()}</td>
                    <td className="rc-td">
                      <span className="mg-ff-pick">
                        <i
                          style={{
                            background: list.find((x) => x.id === sent[r.value])?.color ?? "transparent",
                          }}
                        />
                        <Choice
                          label={`${g.ffGroup}: ${r.value || g.blank}`}
                          hideLabel
                          value={sent[r.value] ?? NONE}
                          options={groupOptions}
                          onChange={(id) => {
                            const to = id === NEW ? addGroup(r.value) : id;
                            const next = { ...sent };
                            if (to === NONE) delete next[r.value];
                            else next[r.value] = to;
                            setSent(next);
                          }}
                        />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(vals.data?.more ?? 0) > 0 && <p className="rc-sub">{g.ffMore(vals.data?.more ?? 0)}</p>}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {g.cancel}
            </Button>
            <Button className="button button-primary" onPress={done}>
              {g.ffApply}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
