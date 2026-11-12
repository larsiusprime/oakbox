/** Model groups' map of the parcel shapes, coloured by group or by what moved, and the parcel inspector. */

import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer, PolygonLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type * as maplibregl from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { api, type GroupsPreview, type ModelGroup, type ParcelInspect, unwrap } from "../api/client";
import { CloseButton } from "../components/Buttons";
import { Tick } from "../components/Form";
import { MapInstruction } from "../components/MapInstruction";
import { type Bounds, boundsOf, MapView, rgba } from "../components/MapView";
import { Seg } from "../components/Seg";
import { Val } from "../components/Val";
import { NO_COLOUR } from "../lib/colours";
import { levelFor } from "../lib/detail";
import { money, short } from "../lib/format";
import { clearGroups, type GroupMap as GroupMapState, publishGroups, setGroupMap } from "../lib/groupmap";
import { useResolved } from "../lib/machine";
import { useTakeOver } from "../lib/mapstep";
import { type BinaryShapes, readShapes, shapeSize, shapesBounds, toBinary } from "../lib/shapes";
import { t } from "../wording";

const g = t.groups;

export type MapMode = "docked" | "full" | "hidden";
export type ColourBy = "group" | "changes";
export const CHANGE_GREY = "#d9dcd4";
export const SAME = "__same";
// Map detail Auto (lib/detail.ts, SPEC §5): every shape up to this many parcels; above it, squares, and zoomed in to
// this many or fewer in view, the shapes in view.
const SHAPES_ALL = 20_000;
const SHAPES_IN_VIEW = 5_000;
// Scattered specks of shapes (shapes.ts: some parcel files hold only a small square at each parcel's point) smaller
// than this on screen fill no pixel: drawn as dots, or with Parcel shapes chosen, drawn at least this size.
const SHAPE_MIN_PX = 3;
type Centre = [number, number] | null;
const NONE: [number, number, number, number] = [0, 0, 0, 0];
const parcelOf = (f: unknown) => (f as { properties: { parcel: number } }).properties.parcel;

type Look = (i: number) => { fill: [number, number, number, number] } | null;
type Square = { polygon: [number, number][]; fill: [number, number, number, number]; mixed: boolean };

/** The parcels in squares of `level` metres, each its parcels' most common colour (group, or what moved); a square
 * where under 80% share it, outlined in white: a mixed place to zoom into. A square clicked is zoomed to. */
function groupSquares(all: Centre[], look: Look, level: number, onSquare: (b: Bounds) => void): Layer[] {
  let lat = 0;
  let k = 0;
  for (const c of all)
    if (c) {
      lat += c[1];
      k++;
    }
  const lat0 = ((k ? lat / k : 0) * Math.PI) / 180;
  const dx = level / (111_320 * Math.cos(lat0));
  const dy = level / 110_540;
  const acc = new Map<string, { n: number; fills: Map<string, { c: number; fill: Square["fill"] }> }>();
  for (let i = 0; i < all.length; i++) {
    const c = all[i];
    const l = c && look(i);
    if (!c || !l) continue;
    const key = `${Math.floor(c[0] / dx)}:${Math.floor(c[1] / dy)}`;
    let a = acc.get(key);
    if (!a) {
      a = { n: 0, fills: new Map() };
      acc.set(key, a);
    }
    a.n++;
    const f = `${l.fill[0]},${l.fill[1]},${l.fill[2]}`;
    const was = a.fills.get(f);
    if (was) was.c++;
    else a.fills.set(f, { c: 1, fill: l.fill });
  }
  const squares: Square[] = [];
  for (const [key, a] of acc) {
    const [gx = 0, gy = 0] = key.split(":").map(Number);
    const top = [...a.fills.values()].sort((p, q) => q.c - p.c)[0];
    if (!top) continue;
    const x0 = gx * dx;
    const y0 = gy * dy;
    squares.push({
      polygon: [
        [x0, y0],
        [x0 + dx, y0],
        [x0 + dx, y0 + dy],
        [x0, y0 + dy],
      ],
      fill: [top.fill[0], top.fill[1], top.fill[2], Math.max(top.fill[3], 200)],
      mixed: top.c < 0.8 * a.n,
    });
  }
  return [
    new SolidPolygonLayer<Square>({
      id: `squares-${level}`,
      data: squares,
      pickable: true,
      getPolygon: (q) => q.polygon,
      getFillColor: (q) => q.fill,
      onClick: ({ object }) => {
        const p = (object as Square | undefined)?.polygon;
        if (p?.[0] && p[2]) onSquare([p[0], p[2]]);
      },
    }),
    new PolygonLayer<Square>({
      id: `squares-mixed-${level}`,
      data: squares.filter((q) => q.mixed),
      filled: false,
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 2,
      getLineColor: [255, 255, 255, 220],
      getPolygon: (q) => q.polygon,
    }),
  ];
}

/** The parcel shapes on OpenStreetMap (when online), coloured by group or by what moved. */
export function ParcelMap({
  projectId,
  preview,
  colours,
  ids,
  hidden,
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
  ids: string[];
  hidden: Set<string>;
  unassigned: string;
  colourBy: ColourBy;
  highlight: number[] | null;
  picked: number | null;
  mode: MapMode;
  onPick: (i: number) => void;
}) {
  const detail = useResolved().map_detail;
  const centres = useQuery({
    queryKey: ["group-centres", projectId],
    queryFn: async () => {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/groups/centres`);
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as Centre[];
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
  const n = centres.data?.length ?? 0;
  // Squares, or Auto on a big county: drawn from the parcels' centres, following the view. Otherwise every shape.
  const byCentres = detail === "squares" || (detail === "auto" && n > SHAPES_ALL);
  // Auto: zoomed in far enough, the parcels in view (few enough) are drawn as shapes.
  const [inView, setInView] = useState<number[] | null>(null);
  const shapes = useQuery({
    queryKey: ["group-shapes", projectId],
    queryFn: async () => {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/groups/shapes`);
      if (!r.ok) throw new Error(await r.text());
      return readShapes(await r.arrayBuffer());
    },
    staleTime: Number.POSITIVE_INFINITY,
    enabled:
      detail === "parcels" ||
      (detail === "auto" && centres.isSuccess && (n <= SHAPES_ALL || inView !== null)),
  });
  const sh = shapes.data;
  const whole = useMemo(() => (sh ? toBinary(sh) : null), [sh]);
  const bounds = useMemo(
    () =>
      centres.data
        ? boundsOf(centres.data.filter((c): c is [number, number] => !!c))
        : sh
          ? (shapesBounds(sh) ?? null)
          : null,
    [centres.data, sh],
  );

  const size = useMemo(() => (sh ? shapeSize(sh) : null), [sh]);
  // Metres a pixel covers now (MapLibre's 512-pixel tiles), for whether the shapes would show, and the squares' size.
  const [perPixel, setPerPixel] = useState<number | null>(null);
  const specks = !!size?.scattered && perPixel != null && size.metres / perPixel < SHAPE_MIN_PX;
  // Parcels chosen: shapes, always (specks drawn bigger). Otherwise specks are dots.
  const swell = specks && detail === "parcels";
  const level = levelFor(perPixel ?? 1000);

  // Which parcels are in view, when few enough to draw as shapes.
  const centresNow = useRef<Centre[] | undefined>(undefined);
  useEffect(() => {
    centresNow.current = centres.data;
  }, [centres.data]);
  // The map, once made: kept as state (a square clicked zooms it; the centres coming late look at it).
  const [mapObj, setMapObj] = useState<maplibregl.Map | null>(null);
  const watch = useCallback((m: maplibregl.Map | null) => {
    setMapObj(m);
    if (!m) return;
    const look = () => {
      const lat = (m.getCenter().lat * Math.PI) / 180;
      setPerPixel((40_075_016.686 * Math.cos(lat)) / (512 * 2 ** m.getZoom()));
      const all = centresNow.current;
      if (!all) return;
      const b = m.getBounds();
      const seen: number[] = [];
      for (let i = 0; i < all.length; i++) {
        const c = all[i];
        if (c && b.contains(c)) {
          seen.push(i);
          if (seen.length > SHAPES_IN_VIEW) return setInView(null);
        }
      }
      setInView(seen);
    };
    m.on("moveend", look);
    m.once("load", look);
  }, []);
  // The centres came after the map: looked at now.
  useEffect(() => {
    if (mapObj && centres.data) mapObj.fire("moveend");
  }, [mapObj, centres.data]);

  // Each parcel's look: its group's colour (grey when it didn't move), dimmed off the highlight, hidden when its
  // legend entry is switched off.
  const look = useMemo(() => {
    const assign = preview?.assign;
    const saved = preview?.saved;
    const hl = highlight ? new Set(highlight) : null;
    return (i: number) => {
      const a = assign?.[i] ?? -1;
      let fill = a >= 0 ? (colours[a] ?? unassigned) : unassigned;
      const unchanged = colourBy === "changes" && a === (saved?.[i] ?? -1);
      if (unchanged) fill = CHANGE_GREY;
      const key = unchanged ? SAME : a >= 0 ? (ids[a] ?? "") : "";
      if (hidden.has(key)) return null;
      const dim = !!hl && !hl.has(i);
      return {
        fill: rgba(fill, dim ? 0.18 : 0.72),
        line: hl?.has(i) ? rgba("#111111") : rgba("#ffffff", dim ? 0.3 : 0.9),
        width: hl?.has(i) ? 1.4 : 0.4,
      };
    };
  }, [preview, colours, ids, hidden, unassigned, colourBy, highlight]);

  // What's drawn: squares (Squares; Auto on a big county until few enough are in view), else shapes.
  const seen = byCentres && detail === "auto" ? inView : null;
  const squares = byCentres && !(seen && sh);
  const layers = useMemo(() => {
    const shapesLayer = (data: BinaryShapes) =>
      new GeoJsonLayer({
        id: "parcels",
        data: data as never,
        pickable: true,
        stroked: true,
        filled: true,
        lineWidthUnits: "pixels",
        lineWidthMinPixels: swell ? SHAPE_MIN_PX : 0,
        getFillColor: (f) => look(parcelOf(f))?.fill ?? NONE,
        getLineColor: (f) => {
          const l = look(parcelOf(f));
          return !l ? NONE : swell ? l.fill : l.line;
        },
        getLineWidth: (f) => look(parcelOf(f))?.width ?? 0,
        updateTriggers: { getFillColor: look, getLineColor: [look, swell], getLineWidth: look },
        // A pick's index is its parcel's (shapes.ts). A parcel switched off in the legend isn't there to click.
        onClick: ({ index }) => {
          if (index >= 0 && look(index)) onPick(index);
        },
      });
    const dotsLayer = (all: Centre[], idx: number[]) =>
      new ScatterplotLayer<number>({
        id: "dots",
        data: idx,
        pickable: true,
        radiusUnits: "pixels",
        getRadius: 2.5,
        getPosition: (i) => all[i] as [number, number],
        getFillColor: (i) => look(i)?.fill ?? NONE,
        updateTriggers: { getFillColor: look },
        onClick: ({ object }) => {
          if (object != null && look(object)) onPick(object);
        },
      });
    const out: Layer[] = [];
    const all = centres.data;
    let drawnAsShapes = false;
    if (squares && all) {
      out.push(...groupSquares(all, look, level, (b) => mapObj?.fitBounds(b, { padding: 24, maxZoom: 17 })));
    } else if (specks && !swell && all) {
      // Specks too small to see: a dot at each parcel's centre.
      out.push(dotsLayer(all, seen ?? all.flatMap((c, i) => (c ? [i] : []))));
    } else if (seen && sh) {
      out.push(shapesLayer(toBinary(sh, seen)));
      drawnAsShapes = true;
    } else if (whole) {
      out.push(shapesLayer(whole));
      drawnAsShapes = true;
    }
    const outline = picked != null && drawnAsShapes && sh ? toBinary(sh, [picked]) : null;
    if (outline && outline.polygons.polygonIndices.value.length > 1)
      out.push(
        new GeoJsonLayer({
          id: "picked",
          data: outline as never,
          stroked: true,
          filled: false,
          lineWidthUnits: "pixels",
          getLineColor: [0, 0, 0, 255],
          getLineWidth: 3,
        }),
      );
    else if (picked != null && all?.[picked])
      out.push(
        new ScatterplotLayer<[number, number]>({
          id: "picked",
          data: [all[picked] as [number, number]],
          radiusUnits: "pixels",
          getRadius: 6,
          stroked: true,
          filled: false,
          lineWidthUnits: "pixels",
          getLineWidth: 2,
          getLineColor: [0, 0, 0, 255],
          getPosition: (c) => c,
        }),
      );
    return out;
  }, [squares, specks, swell, level, mapObj, centres.data, seen, sh, whole, look, picked, onPick]);

  const ready = byCentres ? !!centres.data : !!sh;
  const failed = (byCentres ? centres.error : shapes.error)?.message;
  return (
    <div className="mg-map-body">
      {ready && (
        <MapView
          className="mg-mapview"
          label={g.mapLabel}
          layers={layers}
          bounds={bounds}
          fitKey="parcels"
          resizeKey={mode}
          onMap={watch}
          detail={centres.data ? { squares, parcels: n } : undefined}
        />
      )}
      {!ready && <p className="mg-map-msg">{failed ?? g.loadingMap}</p>}
    </div>
  );
}

export function Inspector({
  projectId,
  groups,
  index,
  name,
  colour,
  currency,
  onShow,
  onClose,
}: {
  projectId: string;
  groups: ModelGroup[];
  index: number;
  name: (id: string) => string;
  colour: (id: string) => string;
  currency: string;
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
    <section className="mg-pop" aria-label={v ? g.parcel({ key: v.key }) : g.parcel({ key: "" })}>
      <div className="mg-pop-head">
        <b className="mg-pop-title">{v ? g.parcel({ key: short(v.key) }) : "…"}</b>
        {v && (
          <span className="mg-tag" style={{ background: colour(v.group) }}>
            {name(v.group)}
          </span>
        )}
        <CloseButton label={g.close} onPress={onClose} />
      </div>
      {q.error && <p className="error">{q.error.message}</p>}
      {v && (
        <>
          <table className="mg-pop-tbl">
            <tbody>
              {v.fields.map((f) => (
                <tr key={f.label}>
                  <td className="mg-pop-k">{f.label}</td>
                  <td className="mg-pop-v">
                    <Val v={f.value} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <b className="mg-pop-sub">{v.group ? g.whyIn({ name: name(v.group) }) : g.whyNone}</b>
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
                  {s.date} · {money(s.price, currency)}
                  {s.vacant ? ` · ${g.vacantSale}` : ""}
                </li>
              ))}
            </ul>
          )}
          {v.like_text && v.like.length > 1 && (
            <div className="mg-live">
              <span>{g.like({ n: v.like.length, sold: v.like_sold, what: v.like_text })}</span>
              <Button className="button button-small" onPress={() => onShow(v.like)}>
                {g.showLike}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** What the groups as edited would do: each parcel's group, each group's counts, what moved. */
export function usePreview(projectId: string, groups: ModelGroup[], enabled = true) {
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

/** What each colour is, and whether it's shown: each square is a checkbox, hollow when its parcels are hidden. */
export function Legend({
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

/** Build the groups, drawn in the map window (SPEC §3.15): the groups as edited on the step, coloured by group or by
 * what moved, a parcel clicked to inspect, the legend's entries switched on and off. */
export function GroupsOnMap({ gm }: { gm: GroupMapState }) {
  const { projectId, groups, unassigned, currency, colourBy, highlight } = gm;
  const hidden = useMemo(() => new Set(gm.hidden), [gm.hidden]);
  const [picked, setPicked] = useState<number | null>(null);
  const preview = usePreview(projectId, groups);
  const colours = useMemo(() => groups.map((x) => x.color), [groups]);
  const ids = useMemo(() => groups.map((x) => x.id), [groups]);
  const name = (id: string) => (id === "" ? g.unassigned : (groups.find((x) => x.id === id)?.name ?? id));
  const toggle = (key: string, on: boolean) =>
    setGroupMap({ hidden: on ? gm.hidden.filter((k) => k !== key) : [...gm.hidden, key] });
  return (
    <div className="mapwin-body mapwin-groups">
      <div className="mg-bar">
        <Seg
          value={colourBy}
          options={[
            ["group", g.byGroup],
            ["changes", g.byChanges],
          ]}
          onChange={(c) => setGroupMap({ colourBy: c })}
        />
        {highlight && (
          <span className="mg-hl">
            {g.highlighted({ n: highlight.length })}{" "}
            <Button className="button button-small" onPress={() => setGroupMap({ highlight: null })}>
              {g.clearHighlight}
            </Button>
          </span>
        )}
        <span className="mg-grow" />
        <span className="mg-hint">{g.clickHint}</span>
      </div>
      <div className="mapwin-stage mg-stage">
        <ParcelMap
          projectId={projectId}
          preview={preview.data}
          colours={colours}
          ids={ids}
          hidden={hidden}
          unassigned={unassigned}
          colourBy={colourBy}
          highlight={highlight}
          picked={picked}
          mode="docked"
          onPick={setPicked}
        />
        {picked != null && (
          <Inspector
            projectId={projectId}
            groups={groups}
            index={picked}
            name={name}
            colour={(id) => (id === "" ? unassigned : (groups.find((x) => x.id === id)?.color ?? NO_COLOUR))}
            currency={currency}
            onShow={(n) => setGroupMap({ highlight: n })}
            onClose={() => setPicked(null)}
          />
        )}
      </div>
      <Legend
        items={
          colourBy === "group"
            ? [
                ...groups.map((x) => [x.id, x.color, x.name] as const),
                ["", unassigned, g.unassigned] as const,
              ]
            : [
                ...groups.map((x) => [x.id, x.color, `${g.movesTo} ${x.name}`] as const),
                ["", unassigned, `${g.movesTo} ${g.unassigned}`] as const,
                [SAME, CHANGE_GREY, g.noChanges] as const,
              ]
        }
        hidden={hidden}
        toggle={toggle}
        showAll={() => setGroupMap({ hidden: [] })}
      />
    </div>
  );
}

/** A step that shows the groups as saved on the map window (SPEC §3.15: Model groups' Check them, Tag and write, What
 * each group got; Evaluate's Which groups): its instruction card here, the groups there. */
export function SavedGroupsOnMap({
  projectId,
  currency,
  title,
}: {
  projectId: string;
  currency: string;
  /** The step's name, on the map's banner. */
  title: string;
}) {
  const q = useQuery({
    queryKey: ["groups", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/groups", { params: { path: { project_id: projectId } } }),
      ),
  });
  const v = q.data;
  useTakeOver(projectId, "groups", title, g.savedOnMap);
  useEffect(() => {
    if (v) publishGroups({ projectId, groups: v.groups, unassigned: v.unassigned_color, currency });
  }, [projectId, v, currency]);
  useEffect(() => () => clearGroups(), []);
  return <MapInstruction title={g.savedOnMap} sub={g.savedOnMapSub} />;
}
