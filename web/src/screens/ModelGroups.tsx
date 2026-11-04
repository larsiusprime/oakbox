import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Map as MapIcon, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay, Radio, RadioGroup } from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type GroupField,
  type GroupsPreview,
  type GroupsView,
  type ModelGroup,
  unwrap,
} from "../api/client";
import { stepChanged, useStep, useStepAct, useStepNav } from "../api/steps";
import { AddButton } from "../components/AddButton";
import { DeleteButton, ToolButton } from "../components/Buttons";
import { Choice, Tick } from "../components/Form";
import { Seg } from "../components/Seg";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { InfoTip } from "../components/Tip";
import { Val } from "../components/Val";
import { when } from "../lib/format";
import { useSettled } from "../lib/hooks";
import { offerUndo } from "../lib/undo";
import { t } from "../wording";
import { AssembleResults, Formats } from "./Assemble";
import { GroupEditor, useValues } from "./GroupEditor";
import { CHANGE_GREY, type ColourBy, Inspector, type MapMode, ParcelMap, SAME } from "./GroupMap";

const g = t.groups;

function useGroups(projectId: string) {
  return useQuery({
    queryKey: ["groups", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/groups", { params: { path: { project_id: projectId } } }),
      ),
  });
}

type MgStep = "start" | "build" | "check" | "write" | "results";
const STEPS: MgStep[] = ["start", "build", "check", "write", "results"];

function usePreview(projectId: string, groups: ModelGroup[], enabled = true) {
  return useQuery({
    queryKey: ["groups-preview", projectId, groups],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/groups/preview", {
          params: { path: { project_id: projectId } },
          body: { groups },
        }),
      ),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** Step 2, Model groups (SPEC §3.5), one task at a time: how to start, the builder, the checks, tag and write
 * (notebook 1's end), and what each group got; Looks right moves on to Check sales. */
export function ModelGroupsTab({ projectId, currency }: { projectId: string; currency: string }) {
  const queryClient = useQueryClient();
  const state = useGroups(projectId);
  const run = useStep("assemble", projectId);
  const act = useStepAct("assemble", projectId);
  // The step shown; after: a run was started from here, so its results open when it's done.
  const nav = useStepNav<MgStep>();
  // Starting again replaces the groups: asked first.
  const [replace, setReplace] = useState<"scratch" | "suggested" | null>(null);
  // How to start: chosen, then Start.
  const [how, setHow] = useState<"suggested" | "scratch" | null>(null);
  const start = useMutation({
    mutationFn: async (how: "scratch" | "suggested") =>
      unwrap(
        await api.POST("/api/projects/{project_id}/groups/start", {
          params: { path: { project_id: projectId } },
          body: { how },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["groups", projectId], data);
      stepChanged(queryClient, projectId, "assemble");
      setReplace(null);
      nav.go("build");
    },
  });
  // Which groups are modeled: saved with the groups; the steps after follow.
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
      stepChanged(queryClient, projectId, "clean");
    },
  });
  const v = state.data;
  const a = run.data;
  const saved = v?.groups ?? [];
  const preview = usePreview(projectId, saved, !!v?.start && saved.length > 0);
  if (!v || !a) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  if (!v.ready) return <p className="bi-lede mg-pad">{g.notReady}</p>;

  const running = a.status === "running";
  const fresh = !!a.receipt && !a.stale;
  const p = preview.data;
  // A group not modeled has nothing left to look at.
  const worst = (p?.stats ?? [])
    .filter((x) => x.modeled || x.id === "")
    .flatMap((x) => x.checks)
    .reduce(
      (w, c) => (c.level === "bad" ? "bad" : c.level === "warn" && w !== "bad" ? "warn" : w),
      "ok" as "ok" | "warn" | "bad",
    );
  const fallback: MgStep = !v.start
    ? "start"
    : running
      ? "write"
      : fresh
        ? "results"
        : saved.length
          ? "write"
          : "build";
  const current = nav.current(a.status, fallback, "results");
  const go = nav.go;
  const steps: Step[] = STEPS.map((key) => ({
    key,
    title: g.steps[key],
    status:
      key === "start"
        ? v.start
          ? "done"
          : "blank"
        : key === "build"
          ? saved.length
            ? "done"
            : "blank"
          : key === "check"
            ? !saved.length
              ? "blank"
              : worst === "ok"
                ? "done"
                : "attention" // nothing here stops the run: ❌ is for what does
            : key === "write"
              ? a.receipt
                ? a.stale
                  ? "attention"
                  : "done"
                : "blank"
              : a.accepted
                ? "done"
                : "blank",
    disabled:
      (key !== "start" && !v.start) ||
      ((key === "check" || key === "write") && !saved.length) ||
      (key === "results" && !a.receipt),
  }));
  const kicker = g.kicker;
  const prev = STEPS[STEPS.indexOf(current) - 1];
  const back = prev ? () => go(prev) : null;
  const toSales = () => navigate({ name: "project", id: projectId, tab: "sales" });
  // Run, and open the results when it's done.
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("write") });

  return (
    <StepFrame steps={steps} current={current} go={go} landing="groups" wide={current === "build"}>
      {current === "start" && (
        <>
          <StepBody kicker={kicker} title={g.startTitle} lede={g.lede}>
            {v.start && <p className="wiz-note">{g.startedWith({ how: v.start })}</p>}
            {/* A choice, then Start: cards that acted at once read as neither a choice nor a button. */}
            <RadioGroup
              aria-label={g.startTitle}
              className="cu-choices mg-start-cards"
              value={how}
              onChange={(x) => setHow(x as "suggested" | "scratch")}
            >
              <Radio value="suggested" className="radio cu-choice" isDisabled={!v.can_suggest}>
                <span className="radio-dot" aria-hidden="true" />
                <span className="cu-text">
                  <b>{g.suggested}</b>
                  <span className="cu-sub">{v.can_suggest ? g.suggestedHelp : g.noSuggest}</span>
                </span>
              </Radio>
              <Radio value="scratch" className="radio cu-choice">
                <span className="radio-dot" aria-hidden="true" />
                <span className="cu-text">
                  <b>{g.scratch}</b>
                  <span className="cu-sub">{g.scratchHelp}</span>
                </span>
              </Radio>
            </RadioGroup>
            <div className="form-actions">
              <Button
                className="button button-primary"
                isDisabled={!how || start.isPending}
                onPress={() => how && (saved.length ? setReplace(how) : start.mutate(how))}
              >
                {g.startButton}
              </Button>
            </div>
            {replace && (
              <div className="bi-warn mg-replace" role="alert">
                {g.replaceWarn({ n: saved.length })}{" "}
                {/* Already the question: the answer that deletes the saved groups carries the trash can. */}
                <Button className="button button-danger" onPress={() => start.mutate(replace)}>
                  <Trash2 aria-hidden="true" size="1em" />
                  {g.replaceYes}
                </Button>{" "}
                <Button className="button" onPress={() => setReplace(null)}>
                  {g.replaceNo}
                </Button>
              </div>
            )}
            {start.error && (
              <p className="error" role="alert">
                {start.error.message}
              </p>
            )}
          </StepBody>
          <StepFoot
            next={v.start ? { label: t.step.next, onPress: () => go("build") } : null}
            note={v.start ? null : g.pickStart}
          />
        </>
      )}
      {current === "build" && (
        <Builder projectId={projectId} currency={currency} view={v} back={back} onward={() => go("check")} />
      )}
      {current === "check" && (
        <>
          <StepBody kicker={kicker} title={g.checkTitle} lede={g.checkLede}>
            <Checks
              groups={saved}
              preview={p}
              unassignedColor={v.unassigned_color}
              edit={() => go("build")}
              setModeled={(id, modeled) =>
                save.mutate(saved.map((x) => (x.id === id ? { ...x, modeled } : x)))
              }
            />
            {save.error && (
              <p className="error" role="alert">
                {save.error.message}
              </p>
            )}
          </StepBody>
          <StepFoot back={back} next={{ label: t.step.next, onPress: () => go("write") }} />
        </>
      )}
      {current === "write" && (
        <>
          <StepBody kicker={kicker} title={g.writeTitle} lede={g.run.what}>
            {running ? (
              <RunProgress job={a.job} lastSeconds={a.receipt?.seconds ?? null} />
            ) : (
              <>
                {a.status === "failed" && (
                  <p className="error" role="alert">
                    {g.run.failed({ e: a.job?.error ?? "" })}
                  </p>
                )}
                {a.blocked.map((b) => (
                  <p key={b} className="wiz-warn">
                    {b}
                  </p>
                ))}
                {a.receipt && (
                  <p className={a.stale ? "wiz-warn" : "wiz-ok"}>
                    {a.stale
                      ? g.run.stale
                      : g.run.written({
                          when: when(a.receipt.ran_at),
                          parcels: a.receipt.parcels,
                          groups: a.receipt.groups.filter((x) => x.id !== "UNKNOWN" && x.parcels > 0).length,
                        })}
                  </p>
                )}
                <Formats projectId={projectId} view={a} />
              </>
            )}
            {act.error && (
              <p className="error" role="alert">
                {act.error.message}
              </p>
            )}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: g.run.again, onPress: runIt }] : []}
            next={
              running
                ? { label: g.run.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? { label: t.step.next, onPress: () => go("results") }
                  : {
                      label: a.receipt ? g.run.runAgain : g.run.run,
                      disabled: a.blocked.length > 0 || act.isPending,
                      onPress: runIt,
                    }
            }
          />
        </>
      )}
      {current === "results" && (
        <>
          <StepBody kicker={kicker} title={g.run.title}>
            <AssembleResults projectId={projectId} view={a} groups={saved} />
          </StepBody>
          <StepFoot
            back={back}
            next={
              a.accepted
                ? { label: g.toSales, onPress: toSales }
                : {
                    label: g.looksRightNext,
                    disabled: a.stale || act.isPending,
                    onPress: () => act.mutate("accept", { onSuccess: toSales }),
                  }
            }
            note={a.stale ? g.run.stale : null}
          />
        </>
      )}
    </StepFrame>
  );
}

/** Each saved group's parcels and sales, with what needs a look; Unassigned last. */
function Checks({
  groups,
  preview: p,
  unassignedColor,
  edit,
  setModeled,
}: {
  groups: ModelGroup[];
  preview: GroupsPreview | undefined;
  unassignedColor: string;
  edit: () => void;
  setModeled: (id: string, modeled: boolean) => void;
}) {
  if (!p) return <p className="empty">{t.project.loading}</p>;
  const rows = [
    ...groups.map((x) => [x.id, x.name, x.color] as const),
    ["", g.unassigned, unassignedColor] as const,
  ];
  return (
    <>
      <table className="tbl mg-checks">
        <thead>
          <tr>
            <th className="mg-model">
              <InfoTip label={g.modelIt} text={g.modelItTip} />
            </th>
            <th>{g.run.group}</th>
            <th className="cs-n">{g.run.parcels}</th>
            <th className="cs-n">{g.run.sales}</th>
            <th className="cs-n">{g.run.vacantSales}</th>
            <th>{g.checksCol}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([id, name, color]) => {
            const x = p.stats.find((s) => s.id === id);
            if (!x) return null;
            const look = x.checks.filter((c) => c.level !== "ok");
            const off = id !== "" && !x.modeled;
            return (
              <tr key={id || "unassigned"} className={off ? "not-modeled" : undefined}>
                <td className="mg-model">
                  {id !== "" && (
                    <Tick isSelected={x.modeled} onChange={(on) => setModeled(id, on)}>
                      <span className="sr-only">{`${g.modelIt}: ${name}`}</span>
                    </Tick>
                  )}
                </td>
                <td>
                  <span className="mg-sw ab-sw" style={{ background: color }} />
                  {name}
                </td>
                <td className="cs-n">{x.parcels.toLocaleString()}</td>
                <td className="cs-n">{x.sales.toLocaleString()}</td>
                <td className="cs-n">{x.vacant_sales.toLocaleString()}</td>
                <td>
                  {off ? (
                    g.notModeled
                  ) : look.length === 0 ? (
                    <span className="wiz-ok">✓</span>
                  ) : (
                    look.map((c) => (
                      <div key={c.text} className={`mg-check ${c.level}`}>
                        {c.text}
                      </div>
                    ))
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="wiz-from">
        {g.checkFix}{" "}
        <Button className="button button-small" onPress={edit}>
          {g.backToBuild}
        </Button>
      </p>
    </>
  );
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

function Builder({
  projectId,
  currency,
  view,
  back,
  onward,
}: {
  projectId: string;
  currency: string;
  view: GroupsView;
  back: (() => void) | null;
  onward: () => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ModelGroup[]>(view.groups);
  const [selected, setSelected] = useState<string | null>(view.groups[0]?.id ?? null);
  const [mapMode, setMapMode] = useState<MapMode>("docked");
  const [colourBy, setColourBy] = useState<ColourBy>("group");
  const [picked, setPicked] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<number[] | null>(null);
  // What the legend has switched off: group ids ("" unassigned), or SAME (unchanged, when colouring by changes).
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [fromField, setFromField] = useState(false);
  const dirty = !same(draft, view.groups);

  const asked = useSettled(draft, 200);
  const preview = usePreview(projectId, asked);
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
      // Saved groups can put notebook 1's output out of date, and so every step after it.
      stepChanged(queryClient, projectId, "assemble");
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
  const ids = useMemo(() => asked.map((x) => x.id), [asked]);
  // Unassigned alone: every group off, unassigned on. Clicking it again (or the legend) brings them back.
  const onlyUnassigned = ids.length > 0 && ids.every((id) => hidden.has(id)) && !hidden.has("");
  const toggle = (key: string, on: boolean) => {
    const next = new Set(hidden);
    if (on) next.delete(key);
    else next.add(key);
    setHidden(next);
  };
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
    const nm = g.newName({ n: draft.length + 1 });
    const used = new Set(draft.map((x) => x.color));
    const color =
      view.colors.find((c) => !used.has(c)) ?? view.colors[draft.length % view.colors.length] ?? "#888";
    const first = view.fields[0]?.name ?? "";
    const x: ModelGroup = {
      id: newId(nm, draft),
      name: nm,
      modeled: null,
      color,
      rule: { join: "any", conditions: [{ column: first, op: "isin", values: [] }] },
      numeric: [],
    };
    setDraft([...draft, x]);
    setSelected(x.id);
  };

  const mapShown = mapMode !== "hidden";
  return (
    <>
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
            isSelected={onlyUnassigned}
            onSelect={() => {
              setHighlight(null);
              setHidden(onlyUnassigned ? new Set() : new Set(ids));
              if (!mapShown) setMapMode("docked");
            }}
          />
          <div className="mg-adds add-row">
            <AddButton onPress={add}>{g.addGroup}</AddButton>
            <Button className="button" onPress={() => setFromField(true)}>
              {g.fromField}
            </Button>
          </div>
          <p className="mg-help">{g.orderHelp}</p>
          <div className="mg-save">
            <DeleteButton isDisabled={!dirty} confirm={g.undoConfirm} onDelete={() => setDraft(view.groups)}>
              {g.undo}
            </DeleteButton>
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
                currency={currency}
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
                  const before = draft;
                  setDraft(draft.filter((x) => x.id !== group.id));
                  setSelected(null);
                  offerUndo(t.buttons.removed({ what: name(group.id) }), () => {
                    setDraft(before);
                    setSelected(group.id);
                  });
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
                  {g.highlighted({ n: highlight.length })}{" "}
                  <Button className="button button-small" onPress={() => setHighlight(null)}>
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
              <ToolButton label={g.hide} pressed onPress={() => setMapMode("hidden")}>
                <MapIcon aria-hidden="true" size="1em" />
              </ToolButton>
            </div>
            <ParcelMap
              projectId={projectId}
              preview={p}
              colours={colours}
              ids={ids}
              hidden={hidden}
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
                      ...asked.map((x) => [x.id, x.color, x.name] as const),
                      ["", view.unassigned_color, g.unassigned] as const,
                    ]
                  : [
                      ...asked.map((x) => [x.id, x.color, `${g.movesTo} ${x.name}`] as const),
                      ["", view.unassigned_color, `${g.movesTo} ${g.unassigned}`] as const,
                      [SAME, CHANGE_GREY, g.noChanges] as const,
                    ]
              }
              hidden={hidden}
              toggle={toggle}
              showAll={() => setHidden(new Set())}
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
      <StepFoot
        back={back}
        note={dirty ? g.unsavedNote : null}
        next={{
          label: dirty ? g.saveNext : t.step.next,
          disabled: draft.length === 0 || save.isPending,
          onPress: () => (dirty ? save.mutate(draft, { onSuccess: onward }) : onward()),
        }}
      />
    </>
  );
}

export type Move = GroupsPreview["moves"][number];

/** Parcels in and out of a group since the saved groups. */
function delta(p: GroupsPreview | undefined, id: string): number {
  if (!p) return 0;
  return p.moves.reduce(
    (n: number, m: Move) => n + (m.to_id === id ? m.parcels : 0) - (m.from_id === id ? m.parcels : 0),
    0,
  );
}

/** What each colour is, and whether it's shown: each square is a checkbox, hollow when its parcels are hidden. */
function Legend({
  items,
  hidden,
  toggle,
  showAll,
}: {
  items: readonly (readonly [string, string, string])[];
  hidden: Set<string>;
  toggle: (key: string, on: boolean) => void;
  showAll: () => void;
}) {
  const any = items.some(([key]) => hidden.has(key));
  return (
    // biome-ignore lint/a11y/useSemanticElements: a row of toggle buttons, not a form field set
    <div className="mg-legend" role="group" aria-label={g.legend}>
      {items.map(([key, c, label]) => {
        const on = !hidden.has(key);
        return (
          // Shows or hides the group on the map: a checkbox, with its colour.
          <span key={key} className={on ? "mg-key" : "mg-key off"}>
            <Tick isSelected={on} onChange={(v) => toggle(key, v)}>
              <i className="mg-key-sw" style={{ background: c, borderColor: c }} />
              {label}
            </Tick>
          </span>
        );
      })}
      {any && (
        <Button className="button button-small" onPress={showAll}>
          {g.showAll}
        </Button>
      )}
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
            {g.parcels({ n: stats.parcels })} · {g.sales({ n: stats.sales, v: stats.vacant_sales })}
          </span>
        )}
        {worst && <span className={`mg-check ${worst.level}`}>{worst.text}</span>}
      </Button>
      {(onUp || onDown) && (
        <span className="mg-order">
          <ToolButton label={g.up({ name })} isDisabled={!onUp} onPress={() => onUp?.()}>
            <ArrowUp aria-hidden="true" size="1em" />
          </ToolButton>
          <ToolButton label={g.down({ name })} isDisabled={!onDown} onPress={() => onDown?.()}>
            <ArrowDown aria-hidden="true" size="1em" />
          </ToolButton>
        </span>
      )}
    </li>
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
  // Where each value goes: what the groups already say about this field, until changed here (for this field).
  const said = useMemo(() => {
    const out: Record<string, string> = {};
    for (const x of groups)
      for (const c of x.rule.conditions)
        if (c.column === field && c.op === "isin") for (const v of c.values) out[v] = out[v] ?? x.id;
    return out;
  }, [field, groups]);
  const [edited, setEdited] = useState<{ field: string; sent: Record<string, string> } | null>(null);
  const sent = edited?.field === field ? edited.sent : said;
  const setSent = (next: Record<string, string>) => setEdited({ field, sent: next });
  const vals = useValues(projectId, field);
  const addGroup = (value: string) => {
    const nm = value || g.newName({ n: list.length + 1 });
    const used = new Set(list.map((x) => x.color));
    const x: ModelGroup = {
      id: newId(nm, list),
      name: nm,
      modeled: null,
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
                    <td className="rc-td mono">{r.value ? <Val v={r.value} /> : g.blank}</td>
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
                          label={`${g.ffGroup}: ${r.value ? <Val v={r.value} /> : g.blank}`}
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
          {(vals.data?.more ?? 0) > 0 && <p className="rc-sub">{g.ffMore({ n: vals.data?.more ?? 0 })}</p>}
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
