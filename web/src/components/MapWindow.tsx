/** The map window (SPEC §3.15): one map of the 🌐 Parcel Universe, docked on a side of the main window (or closed),
 * its size set with the divider, remembered on this computer. Zoomed out, the parcels are drawn as cells sized to the
 * zoom (each coloured by its parcels' figure); once a few thousand parcels are in view, their shapes. Coloured by any
 * field of the parcel files, with the histogram's live range as its legend. Tested on Guilford's 220,000 parcels
 * (docs/spec/app.md §3.15): what costs is the number of shapes drawn, so never more than a few thousand. */
import type { Layer, PickingInfo } from "@deck.gl/core";
import { GeoJsonLayer, PolygonLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import { ExternalLink, Maximize2, Minimize2 } from "lucide-react";
import type * as maplibregl from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Button, Header, ListBoxItem, ListBoxSection } from "react-aria-components";
import {
  api,
  type MapColumn,
  type MapInfo,
  type MapProblem,
  type MapProblems,
  type MapSales,
  unwrap,
  type Wizard,
} from "../api/client";
import { desktop } from "../desktop";
import { pct } from "../lib/format";
import { useGroupMap } from "../lib/groupmap";
import {
  askGo,
  type Dock,
  MAX,
  MIN,
  onGo,
  publishWhere,
  type Side,
  setDock,
  sideFor,
  toggleMap,
  useDock,
  useWhere,
} from "../lib/mapdock";
import { setSlot, useMapStep } from "../lib/mapstep";
import { navigate } from "../lib/route";
import { readShapes, type Shapes, toBinary } from "../lib/shapes";
import { RangedBars, useChosenRange } from "../screens/FieldHistogram";
import { GroupsOnMap } from "../screens/GroupMap";
import { CentreOnMap, LocationsOnMap } from "../screens/Location";
import { LayerOnMap, shownLayer } from "../screens/Shapefiles";
import { t } from "../wording";
import { CloseButton, SmallButton, ToolButton } from "./Buttons";
import { Combo, Marked, matches } from "./Combo";
import { MapCard } from "./MapCard";
import { type Bounds, MapView, rgba } from "./MapView";
import { Tip } from "./Tip";
import { LoadingBar, Waiting } from "./Waiting";

const w = t.mapWindow;

/** Shapes once this few parcels are in view (and around it); cells before. */
const SHAPES_UPTO = 8000;
/** Cell sizes in metres, coarsest first: the finest at least 16 pixels across is drawn. */
const LEVELS = [8000, 4000, 2000, 1000, 500, 250, 125, 60, 30];
const CELL_PX = 16;
/** Sequential, light to dark (ColorBrewer YlGnBu): readable on the street map and without it. */
const RAMP: [number, number, number][] = [
  [255, 255, 204],
  [161, 218, 180],
  [65, 182, 196],
  [44, 127, 184],
  [37, 52, 148],
];
/** A category each, most parcels first; "another value" and blank after them. */
const CATS = [
  "#4e79a7",
  "#f28e2b",
  "#e15759",
  "#76b7b2",
  "#59a14f",
  "#edc948",
  "#b07aa1",
  "#ff9da7",
  "#9c755f",
  "#2f5d9b",
  "#8cd17d",
  "#d37295",
];
const OTHER: [number, number, number, number] = [150, 150, 150, 170];
const BLANK: [number, number, number, number] = [255, 255, 255, 0];
const BLANK_LINE: [number, number, number, number] = [120, 120, 120, 90];

// ---------- The window ----------

export function MapWindow({
  projectId,
  tab,
  step,
}: {
  projectId: string;
  /** Where the main window is: what Follow follows. */
  tab: string | null;
  step: string | null;
}) {
  const d = useDock();
  const width = useWindowWidth();
  const side = sideFor(d.side, width);
  const lid = useLidBottom();
  // The page makes room for it: the content's padding on its side (styles.css, html[data-map]).
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--map-frac", String(d.size));
    root.style.setProperty("--lid-bottom", `${lid}px`);
    // Full size, it covers the page; popped out, it isn't here: the page keeps its room.
    if (!d.open || d.out || d.full) return;
    root.dataset.map = side;
    return () => {
      delete root.dataset.map;
    };
  }, [d.open, d.out, d.full, side, d.size, lid]);
  // Ctrl+M opens and closes it (the 🗺 Map button on the plate too).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        toggleMap();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  // Where this window is, for the map popped out to follow; and its card's links, followed here.
  useEffect(() => {
    publishWhere({ projectId, tab, step });
  }, [projectId, tab, step]);
  useEffect(
    () =>
      onGo((x) => {
        if (x.projectId === projectId && x.step)
          navigate({ name: "project", id: projectId, tab: "fields", step: x.step });
      }),
    [projectId],
  );
  // The popped-out window closed (the desktop app says so): the map docks back.
  useEffect(() => {
    const back = () => setDock({ out: false });
    window.addEventListener("oak-map-closed", back);
    return () => window.removeEventListener("oak-map-closed", back);
  }, []);
  if (!d.open || d.out) return null;
  const go = (s: string) => navigate({ name: "project", id: projectId, tab: "fields", step: s });
  return (
    <aside className={`mapwin mapwin-${d.full ? "full" : side}`} aria-label={w.label}>
      {!d.full && <Divider side={side} size={d.size} />}
      <MapPanel
        projectId={projectId}
        dock={d}
        side={side}
        narrow={side !== d.side}
        mode={d.full ? "full" : "docked"}
        tab={tab}
        step={step}
        onGo={go}
      />
    </aside>
  );
}

/** The map popped out (#/map/<project>): the whole window, following the main window's step; its card's links go
 * there. Docked back from either window, this one closes. */
export function MapAlone({ projectId }: { projectId: string }) {
  const d = useDock();
  const here = useWhere();
  const mine = here?.projectId === projectId ? here : null;
  // Docked back (here, or from the main window): this window goes.
  const wasOut = useRef(false);
  useEffect(() => {
    if (d.out) wasOut.current = true;
    else if (wasOut.current) desktop.closeMap();
  }, [d.out]);
  // This window closed: the map docks back in the main one.
  useEffect(() => {
    const gone = () => setDock({ out: false });
    window.addEventListener("pagehide", gone);
    return () => window.removeEventListener("pagehide", gone);
  }, []);
  useEffect(() => {
    document.title = w.alone;
  }, []);
  return (
    <aside className="mapwin mapwin-alone" aria-label={w.label}>
      <MapPanel
        projectId={projectId}
        dock={d}
        side={d.side}
        narrow
        mode="alone"
        tab={mine?.tab ?? null}
        step={mine?.step ?? null}
        onGo={(s) => askGo({ projectId, tab: "fields", step: s })}
      />
    </aside>
  );
}

function useWindowWidth(): number {
  return useSyncExternalStore(
    (l) => {
      window.addEventListener("resize", l);
      return () => window.removeEventListener("resize", l);
    },
    () => window.innerWidth,
  );
}

/** Where the lid (the plate's oak band) ends: the map docked left, right or top starts below it. */
function useLidBottom(): number {
  const [bottom, setBottom] = useState(0);
  useEffect(() => {
    const lid = document.querySelector(".oak-nav");
    if (!lid) return;
    const measure = () => setBottom(Math.round(lid.getBoundingClientRect().height));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(lid);
    return () => ro.disconnect();
  }, []);
  return bottom;
}

/** The edge to drag: the map's share of the window, from a quarter to 70%. */
function Divider({ side, size }: { side: Side; size: number }) {
  const across = side === "left" || side === "right";
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => {
      const f =
        side === "right"
          ? 1 - ev.clientX / window.innerWidth
          : side === "left"
            ? ev.clientX / window.innerWidth
            : side === "bottom"
              ? 1 - ev.clientY / window.innerHeight
              : ev.clientY / window.innerHeight;
      setDock({ size: f });
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const grow = { right: "ArrowLeft", left: "ArrowRight", bottom: "ArrowUp", top: "ArrowDown" }[side];
    const shrink = { right: "ArrowRight", left: "ArrowLeft", bottom: "ArrowDown", top: "ArrowUp" }[side];
    if (e.key === grow) setDock({ size: size + 0.05 });
    else if (e.key === shrink) setDock({ size: size - 0.05 });
  };
  return (
    // biome-ignore lint/a11y/useSemanticElements: a draggable divider; <hr> can't take focus or be dragged
    <div
      className={`mapwin-divider mapwin-divider-${across ? "across" : "down"}`}
      role="separator"
      aria-orientation={across ? "vertical" : "horizontal"}
      aria-label={w.divider}
      aria-valuemin={MIN * 100}
      aria-valuemax={MAX * 100}
      aria-valuenow={Math.round(size * 100)}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    />
  );
}

const SIDES: Side[] = ["left", "top", "bottom", "right"];

function MapPanel({
  projectId,
  dock,
  side,
  narrow,
  mode,
  tab,
  step,
  onGo,
}: {
  projectId: string;
  dock: Dock;
  side: Side;
  narrow: boolean;
  /** Docked on a side, full size in the main window, or alone in a window of its own. */
  mode: "docked" | "full" | "alone";
  tab: string | null;
  step: string | null;
  onGo: (step: string) => void;
}) {
  const popOut = () => {
    const url = `${window.location.origin}${window.location.pathname}#/map/${projectId}`;
    if (desktop.openMap(url, w.alone)) setDock({ out: true, full: false });
  };
  const info = useQuery({
    queryKey: ["map-info", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "making" ? 1500 : false),
    meta: { quiet: true },
  });
  const m = info.data;
  // The wizard (the sidebar's, shared): each step's fields, for Follow; a field loaded there, a new choice here.
  const wizard = useQuery({
    queryKey: ["wizard", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard", { params: { path: { project_id: projectId } } }),
      ),
  });
  const refetch = info.refetch;
  const stamp = wizard.dataUpdatedAt;
  useEffect(() => {
    if (stamp) void refetch();
  }, [stamp, refetch]);
  // The problems the map can show (worked out on the server once a change; a few seconds on a county).
  const problems = useQuery({
    queryKey: ["map-problems", projectId, m?.stamp, stamp],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/problems", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled: m?.status === "ready",
    placeholderData: keepPreviousData,
    meta: { quiet: true },
  });
  const probs = problems.data;
  // The step that sets each field: the card's links.
  const steps = wizard.data?.steps;
  const locations = wizard.data?.locations;
  const stepOf = useCallback(
    (field: string) =>
      steps?.find((s) => s.fields.includes(field))?.key ??
      (locations?.some((l) => l.name === field) ? "location" : null),
    [steps, locations],
  );
  // The project's map layers (Shapefiles) that can be placed: drawn over the parcels when chosen.
  const layerNames = (wizard.data?.layers ?? []).filter((l) => l.projected).map((l) => l.name);
  const target = m ? followed(tab, step, wizard.data, m.fields, m.sales, probs, layerNames) : null;
  // A step that takes the map over (SPEC §3.15), here or in the main window: while following, the map draws the
  // step's own view, its instruction on a banner along the top.
  const ms = useMapStep();
  const gm = useGroupMap();
  const takeOver = dock.follow && ms?.projectId === projectId ? ms : null;
  const onGroups = takeOver?.view === "groups" && gm?.projectId === projectId ? gm : null;
  const following = dock.follow && target !== null && !takeOver;
  // The banner flashes when the screen's instruction card is hovered: drawn again (its key), its animation runs.
  const flashAt = takeOver?.flash ?? 0;
  // Remembered as the map's field: a takeOver with nothing of its own keeps showing the last one followed.
  const followedField = following ? target?.field : undefined;
  useEffect(() => {
    if (followedField) setDock({ field: followedField });
  }, [followedField]);
  const choices = m
    ? [
        ...m.sales.map((k) => ({ id: `sr:${k}`, label: w.sr[k as SrKey] ?? k })),
        ...(probs?.items ?? []).map((x) => ({ id: x.id, label: problemLabel(x) })),
        ...(layerNames.length ? [{ id: LAYERS, label: w.lyAll({ n: layerNames.length }) }] : []),
        ...m.fields,
      ]
    : [];
  const field =
    (following ? choices.find((f) => f.id === target?.field) : null) ??
    choices.find((f) => f.id === dock.field) ??
    m?.fields[0] ??
    null;
  return (
    <div className="mapwin-in">
      <header className="mapwin-head">
        <b className="mapwin-title">🗺 {w.title}</b>
        {!takeOver && m?.status === "ready" && m.fields.length > 0 && (
          <FieldPick
            sales={m.sales}
            problems={probs}
            layers={layerNames.length}
            fields={m.fields}
            value={field?.id ?? null}
            onChange={(id) => setDock({ field: id, follow: false })}
          />
        )}
        <Tip text={dock.follow ? w.followOnTip : w.followOffTip}>
          <Button
            className={`mapwin-follow ${following ? "on" : ""}`}
            aria-pressed={dock.follow}
            onPress={() => setDock({ follow: !dock.follow })}
          >
            {dock.follow
              ? takeOver
                ? w.following({ step: takeOver.title })
                : target
                  ? w.following({ step: target.title })
                  : w.followIdle
              : w.follow}
          </Button>
        </Tip>
        <span className="mapwin-tools">
          {mode === "docked" &&
            !narrow &&
            SIDES.map((s) => (
              <ToolButton
                key={s}
                label={w.dock({ side: s })}
                pressed={s === side}
                onPress={() => setDock({ side: s })}
              >
                <span className={`mapwin-glyph mapwin-glyph-${s}`} aria-hidden="true" />
              </ToolButton>
            ))}
          {mode !== "alone" && (
            <ToolButton
              label={mode === "full" ? w.unfullTip : w.fullTip}
              pressed={mode === "full"}
              onPress={() => setDock({ full: mode !== "full" })}
            >
              {mode === "full" ? (
                <Minimize2 aria-hidden="true" size="1em" />
              ) : (
                <Maximize2 aria-hidden="true" size="1em" />
              )}
            </ToolButton>
          )}
          {mode === "alone" ? (
            <SmallButton onPress={() => setDock({ out: false, open: true })}>{w.dockBack}</SmallButton>
          ) : (
            <ToolButton label={w.popOutTip} onPress={popOut}>
              <ExternalLink aria-hidden="true" size="1em" />
            </ToolButton>
          )}
          <CloseButton
            label={w.close}
            onPress={() => setDock(mode === "alone" ? { open: false, out: false } : { open: false })}
          />
        </span>
      </header>
      {takeOver && (
        <div key={flashAt} className={`mapwin-banner ${flashAt ? "flash" : ""}`} role="status">
          <b>{takeOver.title}:</b> {takeOver.instruction}
        </div>
      )}
      {takeOver ? (
        takeOver.view === "portal" ? (
          mode === "alone" ? (
            <p className="mapwin-msg">{w.portalOut}</p>
          ) : (
            <div className="mapwin-body mapwin-portal" ref={setSlot} />
          )
        ) : takeOver.view === "centre" ? (
          <CentreOnMap projectId={projectId} />
        ) : takeOver.view === "locations" ? (
          (locations ?? []).length ? (
            <LocationsOnMap
              projectId={projectId}
              names={(locations ?? []).map((x) => x.name)}
              pick={takeOver.pick}
            />
          ) : (
            <p className="mapwin-msg">{w.nothingYet}</p>
          )
        ) : takeOver.view === "layers" ? (
          layerNames.length ? (
            <LayerOnMap projectId={projectId} name={shownLayer(takeOver.pick, layerNames)} />
          ) : (
            <p className="mapwin-msg">{w.nothingYet}</p>
          )
        ) : onGroups ? (
          <GroupsOnMap gm={onGroups} />
        ) : (
          <LoadingBar />
        )
      ) : info.error ? (
        <p className="error mapwin-msg">{info.error.message}</p>
      ) : !m ? (
        <Waiting doing={w.loading} className="mapwin-msg" />
      ) : m.status === "none" ? (
        <p className="mapwin-msg">{w.none}</p>
      ) : m.status === "making" ? (
        <Waiting doing={w.making} className="mapwin-msg" />
      ) : m.status === "failed" ? (
        <p className="error mapwin-msg">{w.failed({ error: m.error ?? "" })}</p>
      ) : (
        <MapBody
          projectId={projectId}
          info={m}
          fieldId={field?.id ?? null}
          label={field?.label ?? ""}
          wizardStamp={stamp}
          unplaced={probs?.unplaced ?? 0}
          layerNames={layerNames}
          stepOf={stepOf}
          onGo={onGo}
          side={side}
          size={dock.size}
        />
      )}
    </div>
  );
}

/** The colour picker, in sections, each folded or unfolded by its heading (remembered): the 🌐 Parcel Universe's
 * fields (yours, the Big five first), the 💰 Sales Record's, the problems (IDs), the differences (a 💰 sale's value
 * against its 🌐 parcel's), and the parcel files' other columns (folded to start). Typing finds them all, folded or
 * not. */
function FieldPick({
  sales,
  problems,
  layers,
  fields,
  value,
  onChange,
}: {
  sales: string[];
  problems: MapProblems | undefined;
  /** How many map layers the project has (Shapefiles): one choice shows them all. */
  layers: number;
  fields: MapInfo["fields"];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const folded = new Set(useDock().folded);
  const fold = (k: Fold) => {
    const next = new Set(folded);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setDock({ folded: [...next] });
  };
  // A section's items: all that match while typing; else none while it's folded.
  const shown = <T,>(k: Fold, q: string, items: T[]) => (q.trim() || !folded.has(k) ? items : []);
  const list = (q: string) => fields.filter((f) => matches(f.label, q) || matches(f.file, q));
  const items = (q: string) => ({
    pu: list(q).filter((f) => f.field),
    sr: sales.filter((k) => matches(w.sr[k as SrKey] ?? k, q)),
    problems: (problems?.items ?? []).filter(
      (x) => !x.id.startsWith("pr:differs:") && matches(problemLabel(x), q),
    ),
    differences: (problems?.items ?? []).filter(
      (x) => x.id.startsWith("pr:differs:") && matches(problemLabel(x), q),
    ),
    columns: list(q).filter((f) => !f.field),
    layers: layers > 0 && matches(w.lyAll({ n: layers }), q) ? [LAYERS] : [],
  });
  const totals = items("");
  const all = (q: string) => {
    const x = items(q);
    return [
      ...x.pu.map((f) => f.id),
      ...x.sr.map((k) => `sr:${k}`),
      ...x.problems.map((p) => p.id),
      ...x.differences.map((p) => p.id),
      ...x.layers,
      ...x.columns.map((f) => f.id),
    ];
  };
  const head = (k: Fold, q: string, n: number, title: string) => (
    <Header className="wiz-section-head mapwin-fold-head">
      {q.trim() ? (
        title
      ) : (
        // Not a choice: it folds or unfolds the section in place, the list staying open (the pointer doesn't take
        // the focus from the box).
        <button
          type="button"
          tabIndex={-1}
          className="mapwin-fold"
          aria-expanded={!folded.has(k)}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => fold(k)}
        >
          <span aria-hidden="true">{folded.has(k) ? "▸" : "▾"}</span> {title}{" "}
          {folded.has(k) && <span className="mapwin-fold-n">({n})</span>}
        </button>
      )}
    </Header>
  );
  const option = (id: string, label: string, q: string, mono = false) => (
    <ListBoxItem key={id} id={id} className={`choice-item ${mono ? "mono" : ""}`} textValue={label}>
      <Marked text={label} query={q} />
    </ListBoxItem>
  );
  return (
    <Combo
      label={w.colourBy}
      hideLabel
      className="field choice mapwin-field"
      popoverClassName="popover choice-popover wiz-popover"
      selectedKey={value}
      onChange={onChange}
      count={(q) => [all(q).length, all("").length]}
      first={(q) => all(q)[0] ?? null}
    >
      {(q) => {
        const x = items(q);
        return (
          <>
            {x.pu.length > 0 && (
              <ListBoxSection className="wiz-section">
                {head("pu", q, totals.pu.length, w.puTitle)}
                {shown("pu", q, x.pu).map((f) => option(f.id, f.label, q))}
              </ListBoxSection>
            )}
            {x.sr.length > 0 && (
              <ListBoxSection className="wiz-section">
                {head("sr", q, totals.sr.length, w.srTitle)}
                {shown("sr", q, x.sr).map((k) => option(`sr:${k}`, w.sr[k as SrKey] ?? k, q))}
              </ListBoxSection>
            )}
            {x.problems.length > 0 && (
              <ListBoxSection className="wiz-section">
                {head("problems", q, totals.problems.length, w.prTitle)}
                {shown("problems", q, x.problems).map((p) => option(p.id, problemLabel(p), q))}
              </ListBoxSection>
            )}
            {x.differences.length > 0 && (
              <ListBoxSection className="wiz-section">
                {head("differences", q, totals.differences.length, w.diffTitle)}
                {shown("differences", q, x.differences).map((p) => option(p.id, problemLabel(p), q))}
              </ListBoxSection>
            )}
            {x.layers.length > 0 && (
              <ListBoxSection className="wiz-section">
                {head("layers", q, 1, w.lyTitle)}
                {shown("layers", q, x.layers).map((id) => option(id, w.lyAll({ n: layers }), q))}
              </ListBoxSection>
            )}
            {x.columns.length > 0 && !q.trim() && (
              <ListBoxSection className="wiz-section">
                {head("columns", q, totals.columns.length, w.columnsTitle)}
              </ListBoxSection>
            )}
            {[...new Set(shown("columns", q, x.columns).map((f) => f.file))].map((file) => (
              <ListBoxSection key={file} className="wiz-section">
                <Header className="wiz-section-head">{w.otherColumns({ file })}</Header>
                {x.columns.filter((f) => f.file === file).map((f) => option(f.id, f.label, q, true))}
              </ListBoxSection>
            ))}
          </>
        );
      }}
    </Combo>
  );
}

type Fold = "pu" | "sr" | "problems" | "differences" | "layers" | "columns";

/** The choice that draws every map layer (Shapefiles) over the parcels. */
const LAYERS = "ly:all";

// ---------- Follow ----------

function problemLabel(x: MapProblems["items"][number]): string {
  const share = pctOf(x.count, x.of);
  if (x.id === "pr:blank_ids") return w.prBlankIds({ n: x.count, share });
  if (x.id === "pr:repeated_ids") return w.prRepeatedIds({ n: x.count, share });
  return w.prDiffers({ field: x.label, n: x.count, share });
}

const pctOf = (n: number, of: number) => (of ? pct(n / of) : "");

type SrKey = keyof typeof w.sr;
/** The 💰 Sales Record's steps: what each colours its sales by (the first the project has). */
const SALES_STEPS: Record<string, string[]> = {
  sales: ["price", "year"],
  sale_date: ["year"],
  sales_ids: ["price", "year"],
  sale_price: ["price"],
  valid_sale: ["valid"],
  vacant_sale: ["vacant"],
};

type Target = { title: string; field: string };

/** What the step on screen shows on the map (SPEC §3.15's table): a Data step's field (its first loaded one, in the
 * step's order: Building size its finished area, Age its year built), or null where the step has none yet. */
function followed(
  tab: string | null,
  step: string | null,
  wizard: Wizard | undefined,
  fields: MapInfo["fields"],
  sales: string[],
  problems: MapProblems | undefined,
  layerNames: string[],
): Target | null {
  if (tab !== "fields" || !step || !wizard) return null;
  const s = wizard.steps.find((x) => x.key === step);
  if (!s) return null;
  const title = s.title ?? t.wizard.steps[s.key]?.title ?? s.key;
  // The 🌐 Parcel Universe: its IDs' problems. Sales record fields: the field whose 💰 values differ most.
  const items = problems?.items ?? [];
  if (step === "universe") {
    const x = items.filter((p) => p.on === "pu").sort((a, b) => b.count - a.count)[0];
    return x ? { title, field: x.id } : null;
  }
  // Shapefiles: the project's map layers over the parcels.
  if (step === "shapefiles") return layerNames.length ? { title, field: LAYERS } : null;
  if (step === "as_sold") {
    const x = items
      .filter((p) => p.id.startsWith("pr:differs:"))
      .sort((a, b) => b.count / Math.max(1, b.of) - a.count / Math.max(1, a.of))[0];
    return x ? { title, field: x.id } : null;
  }
  const sr = SALES_STEPS[step];
  if (sr) {
    const k = sr.find((x) => sales.includes(x));
    return k ? { title, field: `sr:${k}` } : null;
  }
  const keys = step === "location" ? wizard.locations.map((l) => l.name) : s.fields;
  for (const k of keys) {
    const f = fields.find((x) => x.field === k);
    if (f) return { title, field: f.id };
  }
  return null;
}

// ---------- What's drawn ----------

const bin = async (url: string) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return r.arrayBuffer();
};

function decode(b64: string): ArrayBuffer {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out.buffer;
}

type View = { w: number; s: number; e: number; n: number; mpp: number };
/** What's drawn for the view: cells of a size, or the parcels' shapes, for a box around the view. */
type Plan = { kind: "cells"; level: number; box: View } | { kind: "shapes"; box: View; ids: number[] };

function MapBody({
  projectId,
  info,
  fieldId,
  label,
  wizardStamp,
  unplaced,
  layerNames,
  stepOf,
  onGo,
  side,
  size,
}: {
  projectId: string;
  info: MapInfo;
  fieldId: string | null;
  label: string;
  /** When the wizard last changed: the sales (their rules, their columns) read again. */
  wizardStamp: number;
  /** Sales whose parcel isn't in the universe: said, as they can't be shown. */
  unplaced: number;
  layerNames: string[];
  stepOf: (field: string) => string | null;
  onGo: (step: string) => void;
  side: Side;
  size: number;
}) {
  const prId = fieldId?.startsWith("pr:") ? fieldId : null;
  const lyOn = fieldId === LAYERS;
  // The map layers' shapes (as the Shapefiles step's own map has them), each read once.
  const lyQueries = useQueries({
    queries: (lyOn ? layerNames : []).map((name) => ({
      queryKey: ["map-layer", projectId, name],
      queryFn: async () =>
        unwrap(
          await api.GET("/api/projects/{project_id}/wizard/layers/{name}/map", {
            params: { path: { project_id: projectId, name } },
          }),
        ),
      staleTime: Number.POSITIVE_INFINITY,
    })),
  });
  const by = fieldId?.startsWith("sr:") ? (fieldId.slice(3) as SrKey) : null;
  const base = `/api/projects/${encodeURIComponent(projectId)}/map`;
  const centres = useQuery({
    queryKey: ["map-centres", projectId, info.stamp],
    queryFn: async () => new Float32Array(await bin(`${base}/centres`)),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const col = useQuery({
    queryKey: ["map-column", projectId, info.stamp, fieldId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/column", {
          params: { path: { project_id: projectId }, query: { field: fieldId ?? "" } },
        }),
      ),
    enabled: !!fieldId && !by && !prId && !lyOn,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const sales = useQuery({
    queryKey: ["map-sales", projectId, info.stamp, wizardStamp],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/sales", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled: !!by || (!!prId && prId.startsWith("pr:differs:")),
    placeholderData: keepPreviousData,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const sold = useMemo(() => (sales.data ? unpackSales(sales.data) : null), [sales.data]);
  const prob = useQuery({
    queryKey: ["map-problem", projectId, info.stamp, wizardStamp, prId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/problem", {
          params: { path: { project_id: projectId }, query: { id: prId ?? "" } },
        }),
      ),
    enabled: !!prId,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const prPaint = useMemo(() => (prId && prob.data ? problemPainter(prob.data) : null), [prId, prob.data]);
  const onSales = prob.data?.on === "sr";
  const [plan, setPlan] = useState<Plan | null>(null);
  // The parcel picked (a parcel, or a sale's dot): its card, and its outline.
  const [picked, setPicked] = useState<number | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  // The map, once made: kept as state (read in what's drawn: a cell clicked zooms it).
  const [mapObj, setMapObj] = useState<maplibregl.Map | null>(null);
  const zoomTo = (b: Bounds) => mapObj?.fitBounds(b, { padding: 24, maxZoom: 17 });
  const shapes = useQuery({
    queryKey: ["map-shapes", projectId, info.stamp],
    queryFn: async () => readShapes(await bin(`${base}/shapes`)),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: plan?.kind === "shapes",
  });

  // The colour of each parcel (and its place 0..1 on the ramp, for a cell's average), from the field and its range.
  const linkKey = `map:${fieldId}`;
  const srSpread = by && sales.data ? spreadOf(sales.data, by) : undefined;
  const range = useRangeOf(linkKey, by ? srSpread : col.data);
  const paint = useMemo(
    () =>
      prPaint && !onSales
        ? prPaint
        : by || prId || lyOn
          ? painter(undefined, null)
          : painter(col.data, range),
    [by, prId, lyOn, prPaint, onSales, col.data, range],
  );
  const srPaint = useMemo(
    () => (prPaint && onSales ? prPaint : by && sold ? salesPainter(sold, by, range) : null),
    [by, sold, range, prPaint, onSales],
  );

  // Following the view: a new plan only when the view leaves the last one's box, or the zoom wants another size.
  const xy = centres.data;
  const xyNow = useRef(xy);
  useEffect(() => {
    xyNow.current = xy;
  }, [xy]);
  const planNow = useRef(plan);
  useEffect(() => {
    planNow.current = plan;
  }, [plan]);
  const lookNow = useRef<(() => void) | null>(null);
  // Given to the map once, when it's made (MapView's onMap): what follows the view.
  const watch = (m: maplibregl.Map | null) => {
    setMapObj(m);
    if (!m) {
      lookNow.current = null;
      return;
    }
    let frame = 0;
    const look = () => {
      frame = 0;
      const all = xyNow.current;
      if (!all) return;
      const b = m.getBounds();
      const lat = (m.getCenter().lat * Math.PI) / 180;
      const v: View = {
        w: b.getWest(),
        s: b.getSouth(),
        e: b.getEast(),
        n: b.getNorth(),
        mpp: (40_075_016.686 * Math.cos(lat)) / (512 * 2 ** m.getZoom()),
      };
      const next = planFor(v, all, planNow.current);
      if (next !== planNow.current) {
        planNow.current = next;
        setPlan(next);
      }
    };
    lookNow.current = look;
    m.on("move", () => {
      if (!frame) frame = requestAnimationFrame(look);
    });
    m.on("resize", look);
    // Dragging the map: its own hand, not the finger left from what was under the pointer.
    m.on("dragstart", () => {
      m.getCanvas().style.cursor = "";
    });
    m.once("load", look);
  };
  // The centres came after the map: plan now.
  useEffect(() => {
    if (xy) lookNow.current?.();
  }, [xy]);

  // What's drawn (memoized by the React Compiler on what it reads): the parcels (cells or shapes), then the map
  // layers over them when they're chosen.
  const overlays: Layer[] = lyOn
    ? layerNames.flatMap((name, k) => {
        const shapes = lyQueries[k]?.data?.shapes;
        if (!shapes) return [];
        const c = rgba(CATS[k % CATS.length] ?? "#4e79a7", 1);
        return [
          new GeoJsonLayer({
            id: `layer-${name}`,
            data: shapes as never,
            stroked: true,
            filled: true,
            getFillColor: [c[0], c[1], c[2], 50],
            getLineColor: [c[0], c[1], c[2], 230],
            lineWidthUnits: "pixels",
            getLineWidth: 2,
            pointType: "circle",
            pointRadiusUnits: "pixels",
            getPointRadius: 4,
          }),
        ];
      })
    : [];
  const parcels = ((): Layer[] => {
    if (!xy || !plan) return [] as Layer[];
    if (plan.kind === "shapes" && shapes.data) {
      const data = toBinary(shapes.data, plan.ids);
      return [
        new GeoJsonLayer({
          id: "parcels",
          data: data as never,
          pickable: true,
          stroked: true,
          filled: true,
          lineWidthUnits: "pixels",
          getFillColor: (f) => paint.fill(parcelOf(f)),
          getLineColor: (f) => (paint.has(parcelOf(f)) ? [255, 255, 255, 200] : BLANK_LINE),
          getLineWidth: 0.5,
          updateTriggers: { getFillColor: paint, getLineColor: paint },
          onClick: ({ index }) => {
            if (index >= 0) setPicked(index);
          },
        }),
        ...(picked !== null ? [outlineLayer(shapes.data, picked)] : []),
        ...(srPaint && sold ? [dotsLayer(xy, sold, plan.ids, srPaint, setPicked)] : []),
      ];
    }
    const level = plan.kind === "cells" ? plan.level : levelFor(plan.box.mpp);
    return cellsLayer(xy, plan.box, level, srPaint ?? paint, srPaint && sold ? sold : undefined, zoomTo);
  })();
  const layers = [...parcels, ...overlays];

  const bounds = (info.bounds as Bounds | null | undefined) ?? null;
  const tooltip = useCallback(
    (i: PickingInfo) => {
      const o = i.object as { n?: number; parcels?: number; text?: string; sale?: number } | undefined;
      if (o && typeof o.sale === "number" && srPaint && sold) return saleText(sold, o.sale);
      if (o && typeof o.n === "number")
        return srPaint
          ? w.cellSales({ n: o.n, parcels: o.parcels ?? 0 })
          : w.cell({ n: o.n, what: o.text ?? "" });
      if (i.index >= 0 && plan?.kind === "shapes" && !srPaint) return `${label}: ${paint.text(i.index)}`;
      return null;
    },
    [plan, paint, srPaint, sold, label],
  );
  const pinned = useDock().cardPinned;
  const docked = picked !== null && pinned;
  return (
    <div className="mapwin-body">
      {centres.error && <p className="error mapwin-msg">{centres.error.message}</p>}
      <div className="mapwin-stage" ref={stage}>
        <MapView
          className="mapwin-map"
          asked
          label={w.mapLabel}
          layers={layers}
          bounds={bounds}
          fitKey={info.stamp}
          resizeKey={`${side}-${size}-${docked}`}
          onMap={watch}
          tooltip={tooltip}
          cursor={cursorOf}
        />
        {picked !== null && (
          <MapCard
            projectId={projectId}
            index={picked}
            stepOf={stepOf}
            onGo={onGo}
            onColour={(id) => setDock({ field: id, follow: false })}
            pinned={pinned}
            onPin={(on) => setDock({ cardPinned: on })}
            stage={stage}
            onClose={() => setPicked(null)}
          />
        )}
      </div>
      <div className="mapwin-legend">
        {lyOn ? (
          <ul className="mapwin-cats">
            {layerNames.map((name, k) => (
              <li key={name}>
                <span className="mapwin-sw" style={{ background: CATS[k % CATS.length] }} />
                <span className="mono">{name}</span>
                {lyQueries[k]?.isPending && <small>{w.readingLayer}</small>}
                {lyQueries[k]?.error && <small className="error">{lyQueries[k]?.error?.message}</small>}
              </li>
            ))}
          </ul>
        ) : prId ? (
          prob.isPending || (onSales && sales.isPending) ? (
            <Waiting doing={w.readingProblem} />
          ) : prob.error ? (
            <p className="error">{prob.error.message}</p>
          ) : prob.data ? (
            <ul className="mapwin-cats">
              <li>
                <span className="mapwin-sw mapwin-sw-problem" />
                {w.prHas[prob.data.on]({
                  n: prob.data.count,
                  of: prob.data.of,
                  share: pctOf(prob.data.count, prob.data.of),
                })}
              </li>
              <li>
                <span className="mapwin-sw mapwin-sw-hot" />
                {w.prHot}
              </li>
              {onSales && unplaced > 0 && <li className="mapwin-note">{w.unplaced({ n: unplaced })}</li>}
            </ul>
          ) : null
        ) : by ? (
          sales.isPending ? (
            <Waiting doing={w.readingSales} />
          ) : sales.error ? (
            <p className="error">{sales.error.message}</p>
          ) : srSpread && (by === "price" || by === "year") ? (
            <>
              <div className="mapwin-ramp" aria-hidden="true" />
              <RangedBars
                quantiles={srSpread.quantiles}
                count={srSpread.have}
                auto={srSpread.auto}
                year={by === "year"}
                unit=""
                linkKey={linkKey}
                label={w.spread({ field: label })}
              />
              <small className="mapwin-how">
                {w.salesPlaced({ n: sales.data?.placed ?? 0, of: sales.data?.sales ?? 0 })}
              </small>
            </>
          ) : (
            <>
              <div className="mapwin-ramp" aria-hidden="true" />
              <small className="mapwin-share">
                <span>{w.share0[by as "valid" | "vacant"]}</span>
                <span>{w.share1[by as "valid" | "vacant"]}</span>
              </small>
            </>
          )
        ) : col.isPending && fieldId ? (
          <Waiting doing={w.reading} />
        ) : col.error ? (
          <p className="error">{col.error.message}</p>
        ) : col.data?.kind === "number" ? (
          <>
            <div className="mapwin-ramp" aria-hidden="true" />
            <RangedBars
              quantiles={col.data.quantiles}
              count={col.data.have}
              auto={col.data.auto}
              year={/year/i.test(label)}
              unit=""
              linkKey={linkKey}
              label={w.spread({ field: label })}
            />
          </>
        ) : col.data?.kind === "category" ? (
          <ul className="mapwin-cats">
            {col.data.categories.map((c, k) => (
              <li key={c}>
                <span className="mapwin-sw" style={{ background: CATS[k % CATS.length] }} />
                {c} <small>{col.data?.counts[k]?.toLocaleString()}</small>
              </li>
            ))}
            <li>
              <span className="mapwin-sw mapwin-sw-other" />
              {w.other}
            </li>
          </ul>
        ) : null}
        {plan && (
          <small className="mapwin-how">
            {plan.kind === "shapes"
              ? w.howShapes({ n: plan.ids.length })
              : w.howCells({
                  size: plan.level >= 1000 ? `${plan.level / 1000} km` : `${plan.level} m`,
                  sales: by || onSales ? "yes" : "no",
                })}
          </small>
        )}
      </div>
    </div>
  );
}

/** The pointer over the map: a pointing finger over a parcel or a sale (a click picks its parcel), a magnifier over
 * a cell (a click zooms to it), the map's drag hand elsewhere. */
function cursorOf(info: PickingInfo): string {
  const id = info.layer?.id ?? "";
  if (info.index < 0) return "";
  if (id === "parcels" || id === "sales") return "pointer";
  if (id.startsWith("cells-")) return "zoom-in";
  return "";
}

/** A binary feature's parcel (shapes.ts: each corner carries its parcel's index). */
function parcelOf(f: unknown): number {
  const p = (f as { properties?: { parcel?: number } }).properties?.parcel;
  return typeof p === "number" ? p : -1;
}

function levelFor(mpp: number): number {
  return [...LEVELS].reverse().find((s) => s / mpp >= CELL_PX) ?? LEVELS[0] ?? 8000;
}

/** The plan for this view: the last one while it still fits; otherwise shapes when few enough parcels are in a box
 * a quarter of the view's size bigger each side, or cells sized to the zoom. */
function planFor(v: View, xy: Float32Array, last: Plan | null): Plan {
  const level = levelFor(v.mpp);
  if (last) {
    const b = last.box;
    const inside = v.w >= b.w && v.e <= b.e && v.s >= b.s && v.n <= b.n;
    const sameZoom =
      last.kind === "shapes" ? b.mpp / v.mpp < 2.5 && v.mpp / b.mpp < 1.6 : last.level === level;
    if (inside && sameZoom) return last;
  }
  const dx = (v.e - v.w) / 4;
  const dy = (v.n - v.s) / 4;
  const box = { w: v.w - dx, e: v.e + dx, s: v.s - dy, n: v.n + dy, mpp: v.mpp };
  const ids: number[] = [];
  for (let i = 0; i < xy.length / 2; i++) {
    const x = xy[2 * i] ?? Number.NaN;
    const y = xy[2 * i + 1] ?? Number.NaN;
    if (x >= box.w && x <= box.e && y >= box.s && y <= box.n) {
      ids.push(i);
      if (ids.length > SHAPES_UPTO) return { kind: "cells", level, box };
    }
  }
  return { kind: "shapes", box, ids };
}

type Paint = {
  /** A parcel's colour. */
  fill: (i: number) => [number, number, number, number];
  /** Its place on the ramp (numbers, 0 to 1) or its category (0.., -1 another value); null blank. */
  at: (i: number) => number | null;
  has: (i: number) => boolean;
  text: (i: number) => string;
  kind: "number" | "category" | "none";
  /** A problem: the county's share of it, for colouring a cell by its own share and outlining hot spots. */
  county?: number;
};

function ramp(t: number): [number, number, number, number] {
  return rampOf(RAMP, t);
}

function rampOf(stops: [number, number, number][], t: number): [number, number, number, number] {
  const x = Math.min(0.9999, Math.max(0, t)) * (stops.length - 1);
  const k = Math.floor(x);
  const f = x - k;
  const a = stops[k] ?? [0, 0, 0];
  const b = stops[k + 1] ?? a;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 215];
}

function painter(c: MapColumn | undefined, range: { lo: number; hi: number } | null): Paint {
  if (c?.kind === "number" && range) {
    const v = new Float32Array(decode(c.values));
    const log = range.lo > 0 && range.hi / range.lo >= 100;
    const f = log ? Math.log10 : (x: number) => x;
    const lo = f(range.lo);
    const span = f(range.hi) - lo || 1;
    const at = (i: number) => {
      const x = v[i];
      return x === undefined || Number.isNaN(x) ? null : (f(log ? Math.max(x, range.lo) : x) - lo) / span;
    };
    return {
      kind: "number",
      at,
      has: (i) => at(i) !== null,
      fill: (i) => {
        const p = at(i);
        return p === null ? BLANK : ramp(p);
      },
      text: (i) => {
        const x = v[i];
        return x === undefined || Number.isNaN(x) ? w.blank : x.toLocaleString();
      },
    };
  }
  if (c?.kind === "category") {
    const codes = new Uint16Array(decode(c.values));
    const cols = CATS.map((x) => rgba(x, 0.85));
    const at = (i: number) => {
      const k = codes[i] ?? 65535;
      return k === 65535 ? null : k === 65534 ? -1 : k;
    };
    return {
      kind: "category",
      at,
      has: (i) => at(i) !== null,
      fill: (i) => {
        const k = at(i);
        return k === null ? BLANK : k < 0 ? OTHER : (cols[k % cols.length] ?? OTHER);
      },
      text: (i) => {
        const k = at(i);
        return k === null ? w.blank : k < 0 ? w.other : (c.categories[k] ?? "");
      },
    };
  }
  return {
    kind: "none",
    at: () => null,
    has: () => true,
    fill: () => [214, 210, 200, 200],
    text: () => "",
  };
}

type Cell = {
  polygon: [number, number][];
  fill: [number, number, number, number];
  n: number;
  parcels: number;
  text: string;
  hot?: boolean;
};

/** The parcels in the box, in cells of `level` metres: a cell's colour is its parcels' average place on the ramp
 * (numbers) or their most common category. */
function cellsLayer(
  xy: Float32Array,
  box: View,
  level: number,
  paint: Paint,
  sold: Sold | undefined,
  onCell: (b: Bounds) => void,
): Layer[] {
  const lat0 = (((box.s + box.n) / 2) * Math.PI) / 180;
  const dx = level / (111_320 * Math.cos(lat0));
  const dy = level / 110_540;
  type Acc = { parcels: number; n: number; sum: number; have: number; cats: Map<number, number> };
  const acc = new Map<string, Acc>();
  const cellAt = (x: number, y: number): Acc | null => {
    if (!(x >= box.w && x <= box.e && y >= box.s && y <= box.n)) return null;
    const key = `${Math.floor(x / dx)}:${Math.floor(y / dy)}`;
    let c = acc.get(key);
    if (!c) {
      c = { parcels: 0, n: 0, sum: 0, have: 0, cats: new Map() };
      acc.set(key, c);
    }
    return c;
  };
  const add = (c: Acc, k: number) => {
    c.n++;
    const a = paint.at(k);
    if (a === null) return;
    c.have++;
    if (paint.kind === "number") c.sum += a;
    else c.cats.set(a, (c.cats.get(a) ?? 0) + 1);
  };
  // The parcels: what's coloured (🌐), or what's behind the sales (💰), the county's shape.
  for (let i = 0; i < xy.length / 2; i++) {
    const c = cellAt(xy[2 * i] ?? Number.NaN, xy[2 * i + 1] ?? Number.NaN);
    if (!c) continue;
    c.parcels++;
    if (!sold) add(c, i);
  }
  if (sold)
    for (let k = 0; k < sold.n; k++) {
      const p = sold.parcel[k] ?? -1;
      if (p < 0) continue;
      const c = cellAt(xy[2 * p] ?? Number.NaN, xy[2 * p + 1] ?? Number.NaN);
      if (c) add(c, k);
    }
  const cells: Cell[] = [];
  for (const [key, c] of acc) {
    const [gx = 0, gy = 0] = key.split(":").map(Number);
    const x0 = gx * dx;
    const y0 = gy * dy;
    let fill: [number, number, number, number] = [214, 210, 200, 200];
    let text = "";
    let hot = false;
    if (paint.county !== undefined && c.have) {
      const share = c.sum / c.have;
      const t = paint.county > 0 ? Math.min(1, share / (3 * paint.county)) : share > 0 ? 1 : 0;
      fill = rampOf(PROBLEM_RAMP, t);
      hot = c.have >= HOT_MIN && share > 2 * paint.county && share > 0;
      text = w.prCell({ share: pct(share) });
    } else if (paint.kind === "number" && c.have) {
      fill = ramp(c.sum / c.have);
    } else if (paint.kind === "category" && c.have) {
      const [top, k] = [...c.cats.entries()].sort((p, q) => q[1] - p[1])[0] ?? [-1, 0];
      fill = top < 0 ? OTHER : rgba(CATS[top % CATS.length] ?? "#999999", 0.85);
      text = w.mostly({ share: Math.round((100 * k) / c.have) });
    } else if (paint.kind !== "none") fill = [235, 235, 235, sold ? 110 : 160];
    cells.push({
      polygon: [
        [x0, y0],
        [x0 + dx, y0],
        [x0 + dx, y0 + dy],
        [x0, y0 + dy],
      ],
      fill,
      n: sold ? c.n : c.parcels,
      parcels: c.parcels,
      text,
      hot,
    });
  }
  const out: Layer[] = [
    new SolidPolygonLayer<Cell>({
      id: `cells-${level}`,
      data: cells,
      pickable: true,
      getPolygon: (c) => c.polygon,
      getFillColor: (c) => c.fill,
      // A cell clicked: zoomed to, toward its parcels.
      onClick: ({ object }) => {
        const p = (object as Cell | undefined)?.polygon;
        if (p?.[0] && p[2]) onCell([p[0], p[2]]);
      },
    }),
  ];
  // Hot spots: cells with more than twice the county's share of the problem (and enough to say so), outlined.
  const hot = cells.filter((c) => c.hot);
  if (hot.length)
    out.push(
      new PolygonLayer<Cell>({
        id: `hot-${level}`,
        data: hot,
        filled: false,
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 2,
        getLineColor: [90, 30, 0, 255],
        getPolygon: (c) => c.polygon,
      }),
    );
  return out;
}

/** Cells with fewer parcels (or sales) than this aren't called hot spots: a share of a handful says little. */
const HOT_MIN = 30;

/** The range chosen for the legend's histogram (the automatic one until it's set). */
function useRangeOf(key: string, c: MapColumn | undefined): { lo: number; hi: number } | null {
  const chosen = useChosenRange(key);
  if (chosen) return chosen;
  const [lo, hi] = c?.auto ?? [];
  return lo != null && hi != null ? { lo, hi } : null;
}

// ---------- Problems ----------

const PROBLEM: [number, number, number, number] = [222, 107, 26, 235];
const FINE: [number, number, number, number] = [205, 200, 190, 150];
/** Light to dark orange: a cell's share of the problem, against three times the county's. */
const PROBLEM_RAMP: [number, number, number][] = [
  [243, 240, 234],
  [253, 208, 162],
  [253, 141, 60],
  [217, 72, 1],
  [127, 39, 4],
];

/** Each parcel (or sale) with the problem orange, the others grey; a cell by its share of them, the county's share
 * for the hot spots. */
function problemPainter(d: MapProblem): Paint {
  const f = new Int8Array(decode(d.flags));
  const at = (k: number) => {
    const x = f[k] ?? -1;
    return x < 0 ? null : x;
  };
  return {
    kind: "number",
    at,
    has: (k) => at(k) !== null,
    fill: (k) => (at(k) === 1 ? PROBLEM : FINE),
    text: (k) => (at(k) === 1 ? w.prYes : w.prNo),
    county: d.of ? d.count / d.of : 0,
  };
}

// ---------- The 💰 sales ----------

type Sold = {
  n: number;
  parcel: Int32Array;
  price: Float32Array;
  year: Float32Array;
  valid: Int8Array;
  vacant: Int8Array;
};

function unpackSales(d: MapSales): Sold {
  return {
    n: d.sales,
    parcel: new Int32Array(decode(d.parcel)),
    price: new Float32Array(decode(d.price)),
    year: new Float32Array(decode(d.year)),
    valid: new Int8Array(decode(d.valid)),
    vacant: new Int8Array(decode(d.vacant)),
  };
}

/** The legend's spread for price or date: what RangedBars takes, as a field's column gives it. */
function spreadOf(d: MapSales, by: SrKey): MapColumn | undefined {
  if (by !== "price" && by !== "year") return undefined;
  const q = by === "price" ? d.price_quantiles : d.year_quantiles;
  const auto = by === "price" ? d.price_auto : d.year_auto;
  return {
    id: `sr:${by}`,
    kind: "number",
    values: "",
    have: d.placed,
    quantiles: q,
    auto,
    categories: [],
    counts: [],
  };
}

/** Each sale's colour: price or date on the ramp over the range shown; valid or vacant at its two ends (dark: yes),
 * so a cell's average is the share. */
function salesPainter(d: Sold, by: SrKey, range: { lo: number; hi: number } | null): Paint {
  let at: (k: number) => number | null;
  if (by === "price" || by === "year") {
    const v = by === "price" ? d.price : d.year;
    const lo = range?.lo ?? 0;
    const hi = range?.hi ?? 1;
    const log = by === "price" && lo > 0 && hi / lo >= 100;
    const f = log ? Math.log10 : (x: number) => x;
    const span = f(hi) - f(lo) || 1;
    at = (k) => {
      const x = v[k];
      return x === undefined || Number.isNaN(x) ? null : (f(log ? Math.max(x, lo) : x) - f(lo)) / span;
    };
  } else {
    const v = by === "valid" ? d.valid : d.vacant;
    at = (k) => {
      const x = v[k] ?? -1;
      return x < 0 ? null : x;
    };
  }
  return {
    kind: "number",
    at,
    has: (k) => at(k) !== null,
    fill: (k) => {
      const p = at(k);
      return p === null ? [150, 150, 150, 200] : ramp(p);
    },
    text: () => "",
  };
}

/** A year with its fraction (2023.41) as the day, YYYY-MM-DD. */
function dayOf(y: number): string {
  const year = Math.floor(y);
  const d = new Date(Date.UTC(year, 0, 1) + Math.round((y - year) * 365.25) * 86_400_000);
  return d.toISOString().slice(0, 10);
}

function saleText(d: Sold, k: number): string {
  const y = d.year[k];
  const p = d.price[k];
  const bits = [
    y === undefined || Number.isNaN(y) ? null : dayOf(y),
    p === undefined || Number.isNaN(p) ? null : p.toLocaleString(),
    d.valid[k] === 1 ? w.validYes : d.valid[k] === 0 ? w.validNo : null,
    d.vacant[k] === 1 ? w.vacantYes : null,
  ];
  return `💰 ${bits.filter(Boolean).join(" · ")}`;
}

type Dot = { sale: number; position: [number, number] };

/** The sales on the parcels drawn, as dots at their parcels' centres: the latest on top. */
function dotsLayer(
  xy: Float32Array,
  d: Sold,
  ids: number[],
  paint: Paint,
  onPick: (parcel: number) => void,
): Layer {
  const shown = new Set(ids);
  const dots: Dot[] = [];
  for (let k = 0; k < d.n; k++) {
    const p = d.parcel[k] ?? -1;
    if (p >= 0 && shown.has(p)) dots.push({ sale: k, position: [xy[2 * p] ?? 0, xy[2 * p + 1] ?? 0] });
  }
  dots.sort((a, b) => (d.year[a.sale] || 0) - (d.year[b.sale] || 0));
  return new ScatterplotLayer<Dot>({
    id: "sales",
    data: dots,
    pickable: true,
    radiusUnits: "pixels",
    getRadius: 4.5,
    stroked: true,
    lineWidthUnits: "pixels",
    getLineWidth: 1,
    getLineColor: [40, 40, 40, 220],
    getPosition: (o) => o.position,
    getFillColor: (o) => paint.fill(o.sale),
    updateTriggers: { getFillColor: paint },
    onClick: ({ object }) => {
      const p = object ? (d.parcel[(object as Dot).sale] ?? -1) : -1;
      if (p >= 0) onPick(p);
    },
  });
}

/** The parcel picked, outlined. */
function outlineLayer(sh: Shapes, parcel: number): Layer {
  return new GeoJsonLayer({
    id: "picked",
    data: toBinary(sh, [parcel]) as never,
    stroked: true,
    filled: false,
    lineWidthUnits: "pixels",
    getLineColor: [17, 17, 17, 255],
    getLineWidth: 3,
  });
}
