import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, Radio } from "react-aria-components";
import { api, type GroupsPreview, type GroupsView, type ModelGroup, type Move, unwrap } from "../api/client";
import { stepChanged, useStep, useStepAct, useStepNav } from "../api/steps";
import { AddButton } from "../components/AddButton";
import { DeleteButton, ToolButton } from "../components/Buttons";
import { Disclose } from "../components/Disclose";
import { Radios, Tick } from "../components/Form";
import { MapInstruction } from "../components/MapInstruction";
import { Seg } from "../components/Seg";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame, type StepStatus } from "../components/Steps";
import { LoadingBar } from "../components/Waiting";
import { NO_COLOUR } from "../lib/colours";
import { when } from "../lib/format";
import { clearGroups, publishGroups, setGroupMap, useGroupMap } from "../lib/groupmap";
import { newGroup } from "../lib/groups";
import { useSettled } from "../lib/hooks";
import { dockNow, setDock } from "../lib/mapdock";
import { useTakeOver } from "../lib/mapstep";
import { onward as goOnTo } from "../lib/returnto";
import { navigate } from "../lib/route";
import { offerUndo } from "../lib/undo";
import { t } from "../wording";
import { AssembleResults, Formats } from "./Assemble";
import { GroupChecks } from "./GroupChecks";
import { GroupEditor } from "./GroupEditor";
import { GroupFromField } from "./GroupFromField";
import { Legend, SavedGroupsOnMap, usePreview } from "./GroupMap";

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
  // Groups already made: the choice to start again is shown only when asked for.
  const [again, setAgain] = useState(false);
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
  // The one group shown alone on the map, if any (Check them's Show on map).
  const gmNow = useGroupMap();
  const hiddenNow = new Set(gmNow?.hidden ?? []);
  const keys = [...saved.map((x) => x.id), ""];
  const alone =
    keys.filter((k) => !hiddenNow.has(k)).length === 1 ? (keys.find((k) => !hiddenNow.has(k)) ?? null) : null;
  const preview = usePreview(projectId, saved, !!v?.start && saved.length > 0);
  if (!v || !a) return <LoadingBar error={state.error} />;
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
  const have = !!v.start && saved.length > 0;
  const go = nav.go;
  const statusOf = (key: MgStep): StepStatus => {
    switch (key) {
      case "start":
        return v.start ? "done" : "blank";
      case "build":
        return saved.length ? "done" : "blank";
      case "check":
        if (!saved.length) return "blank";
        return worst === "ok" ? "done" : "attention"; // nothing here stops the run: ❌ is for what does
      case "write":
        if (!a.receipt) return "blank";
        return a.stale ? "attention" : "done";
      case "results":
        return a.accepted ? "done" : "blank";
    }
  };
  const steps: Step[] = STEPS.map((key) => ({
    key,
    title: g.steps[key],
    status: statusOf(key),
    disabled:
      (key !== "start" && !v.start) ||
      ((key === "check" || key === "write") && !saved.length) ||
      (key === "results" && !a.receipt),
  }));
  const prev = STEPS[STEPS.indexOf(current) - 1];
  const back = prev ? () => go(prev) : null;
  const toSales = () => goOnTo(projectId, "sales");
  // Run, and open the results when it's done.
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("write") });

  return (
    <StepFrame steps={steps} current={current} go={go} landing="groups" wide={current === "build"}>
      {current === "start" && (
        <>
          <StepBody title={g.startTitle} lede={g.lede}>
            {/* Groups already made: keeping them is the answer; starting again is tucked away, and asks first. */}
            {have && (
              <div className="mg-have">
                <p className="wiz-note">{g.haveGroups({ n: saved.length, how: v.start ?? "scratch" })}</p>
                <div className="form-actions mg-have-actions">
                  <Button className="button button-primary" onPress={() => go("build")}>
                    {g.keepThem} ›
                  </Button>
                </div>
                <Disclose open={again} onPress={() => setAgain(!again)}>
                  {g.startAgain}
                </Disclose>
              </div>
            )}
            {(!have || again) && (
              <>
                {/* A choice, then Start: cards that acted at once read as neither a choice nor a button. */}
                <Radios
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
                </Radios>

                {replace && (
                  <div className="bi-warn mg-replace" role="alert">
                    {g.replaceWarn({ n: saved.length })}{" "}
                    {/* Already the question: the answer that deletes the saved groups carries the trash can. */}
                    <Button className="button button-danger" onPress={() => start.mutate(replace)}>
                      <Trash2 aria-hidden="true" size="1em" />
                      {g.replaceYes}
                    </Button>{" "}
                    <Button
                      className="button"
                      onPress={() => {
                        setReplace(null);
                        go("build");
                      }}
                    >
                      {g.replaceNo}
                    </Button>
                  </div>
                )}
              </>
            )}
            {start.error && (
              <p className="error" role="alert">
                {start.error.message}
              </p>
            )}
          </StepBody>
          {/* Start at the foot, where Next is on every step: what's chosen above starts the groups. */}
          <StepFoot
            next={
              !have || again
                ? {
                    label: g.startButton,
                    onPress: () => how && (saved.length ? setReplace(how) : start.mutate(how)),
                    disabled: !how || start.isPending,
                  }
                : { label: t.step.next, onPress: () => go("build") }
            }
            note={!have && !how ? g.pickStart : null}
          />
        </>
      )}
      {current === "build" && (
        <Builder projectId={projectId} currency={currency} view={v} back={back} onward={() => go("check")} />
      )}
      {current === "check" && (
        <>
          <StepBody title={g.checkTitle} lede={g.checkLede}>
            <SavedGroupsOnMap projectId={projectId} currency={currency} title={g.steps.check} />
            <GroupChecks
              groups={saved}
              preview={p}
              unassignedColor={v.unassigned_color}
              setModeled={(id, modeled) =>
                save.mutate(saved.map((x) => (x.id === id ? { ...x, modeled } : x)))
              }
              onMap={{
                shown: alone,
                // A group (or Unassigned) alone on the map; pressed again, every group back.
                show: (id) =>
                  setGroupMap({
                    hidden: alone === id ? [] : [...saved.map((x) => x.id), ""].filter((k) => k !== id),
                    highlight: null,
                  }),
                all: () => setGroupMap({ hidden: [], highlight: null }),
              }}
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
          <StepBody title={g.writeTitle} lede={g.run.what}>
            <SavedGroupsOnMap projectId={projectId} currency={currency} title={g.steps.write} />
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
          <StepBody title={g.run.title}>
            <SavedGroupsOnMap projectId={projectId} currency={currency} title={g.steps.results} />
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

function same(a: ModelGroup[], b: ModelGroup[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
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
  // The map is the map window's (SPEC §3.15): it's opened, following, and draws the groups as edited here; what the
  // legend has switched off and what's highlighted are shared with it.
  const gm = useGroupMap();
  const hidden = new Set(gm?.hidden ?? []);
  const setHidden = (next: Set<string>) => setGroupMap({ hidden: [...next] });
  const setHighlight = (n: number[] | null) => {
    setGroupMap({ highlight: n });
    if (n && !dockNow().out) setDock({ open: true });
  };
  // A take-over step (SPEC §3.15): the map opens on the groups; leaving, it's given back as it was.
  useTakeOver(projectId, "groups", t.groups.steps.build, g.mapInstruction);
  useEffect(() => () => clearGroups(), []);
  const [fromField, setFromField] = useState(false);
  const dirty = !same(draft, view.groups);

  const asked = useSettled(draft, 200);
  const preview = usePreview(projectId, asked);
  useEffect(() => {
    publishGroups({ projectId, groups: asked, unassigned: view.unassigned_color, currency });
  }, [projectId, asked, view.unassigned_color, currency]);
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
  const ids = asked.map((x) => x.id);
  // Unassigned alone: every group off, unassigned on. Clicking it again (or the legend) brings them back.
  const onlyUnassigned = ids.length > 0 && ids.every((id) => hidden.has(id)) && !hidden.has("");
  // The one group shown alone on the map (every other one, and Unassigned, switched off), if any.
  const isolated =
    ids.find((id) => !hidden.has(id) && hidden.has("") && ids.every((o) => o === id || hidden.has(o))) ??
    null;
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
    const first = view.fields[0]?.name ?? "";
    const x = newGroup(g.newName({ n: draft.length + 1 }), draft, view.colors, [
      { column: first, op: "isin", values: [] },
    ]);
    setDraft([...draft, x]);
    setSelected(x.id);
  };

  return (
    <>
      <div className="mg mg-nomap">
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
                  // As Unassigned does: its parcels alone on the map; clicked again, every group back.
                  setSelected(x.id);
                  setHighlight(null);
                  setHidden(isolated === x.id ? new Set() : new Set([...ids, ""].filter((k) => k !== x.id)));
                  if (!dockNow().out) setDock({ open: true });
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
              if (!dockNow().out) setDock({ open: true });
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

        {
          <div className="mg-ed">
            <MapInstruction title={g.mapInstruction} sub={g.mapInstructionSub} />
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
                byHand={view.by_hand[group.id] ?? []}
                onDelete={() => {
                  const before = draft;
                  setDraft(draft.filter((x) => x.id !== group.id));
                  setSelected(null);
                  offerUndo(t.buttons.removed({ what: name(group.id) }), () => {
                    setDraft(before);
                    setSelected(group.id);
                  });
                }}
                onShow={(n) => setHighlight(n)}
                moved={moved}
              />
            ) : (
              <p className="bi-lede">{g.pickGroup}</p>
            )}
          </div>
        }

        {fromField && (
          <GroupFromField
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

/** Parcels in and out of a group since the saved groups. */
function delta(p: GroupsPreview | undefined, id: string): number {
  if (!p) return 0;
  return p.moves.reduce(
    (n: number, m: Move) => n + (m.to_id === id ? m.parcels : 0) - (m.from_id === id ? m.parcels : 0),
    0,
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
