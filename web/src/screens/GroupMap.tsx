/** Model groups' map of the parcel shapes, coloured by group or by what moved, and the parcel inspector. */

import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type * as maplibregl from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { api, type GroupsPreview, type ModelGroup, type ParcelInspect, unwrap } from "../api/client";
import { CloseButton } from "../components/Buttons";
import { boundsOf, boundsOfGeoJson, MapView, rgba } from "../components/MapView";
import { Val } from "../components/Val";
import { money, short } from "../lib/format";
import { useResolved } from "../lib/machine";
import { t } from "../wording";

const g = t.groups;

export type MapMode = "docked" | "full" | "hidden";
export type ColourBy = "group" | "changes";
export const CHANGE_GREY = "#d9dcd4";
export const SAME = "__same";
// Map detail (Settings › Performance, SPEC §5): "dots above" this many parcels; and zoomed in to this many or fewer,
// the shapes in view are drawn instead of their dots.
const DOTS_ABOVE = 20_000;
const SHAPES_IN_VIEW = 5_000;
type Centre = [number, number] | null;

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
    enabled: detail !== "shapes",
  });
  const n = centres.data?.length ?? 0;
  const dots = detail === "dots" || (detail === "auto" && n > DOTS_ABOVE);
  // Drawn as dots: zoomed in far enough, the parcels in view (few enough) are drawn as shapes.
  const [inView, setInView] = useState<number[] | null>(null);
  const shapes = useQuery({
    queryKey: ["group-shapes", projectId],
    queryFn: async () => {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/groups/shapes`);
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as GeoJSON.FeatureCollection;
    },
    staleTime: Number.POSITIVE_INFINITY,
    enabled: detail === "shapes" || (centres.isSuccess && (!dots || inView !== null)),
  });
  const fc = shapes.data;
  const bounds = useMemo(
    () =>
      dots ? boundsOf((centres.data ?? []).filter((c): c is [number, number] => !!c)) : boundsOfGeoJson(fc),
    [dots, centres.data, fc],
  );

  // Which parcels are in view, when few enough to draw as shapes.
  const centresNow = useRef<Centre[] | undefined>(undefined);
  useEffect(() => {
    centresNow.current = centres.data;
  }, [centres.data]);
  const watch = useCallback((m: maplibregl.Map | null) => {
    if (!m) return;
    const look = () => {
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
  }, []);

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

  const layers = useMemo(() => {
    const idOf = (f: GeoJSON.Feature) => Number(f.id ?? -1);
    const shapesLayer = (features: GeoJSON.Feature[]) =>
      new GeoJsonLayer({
        id: "parcels",
        data: { type: "FeatureCollection", features } as GeoJSON.FeatureCollection,
        pickable: true,
        stroked: true,
        filled: true,
        lineWidthUnits: "pixels",
        getFillColor: (f) => look(idOf(f))?.fill ?? [0, 0, 0, 0],
        getLineColor: (f) => look(idOf(f))?.line ?? [0, 0, 0, 0],
        getLineWidth: (f) => look(idOf(f))?.width ?? 0,
        updateTriggers: { getFillColor: look, getLineColor: look, getLineWidth: look },
        onClick: ({ object }) => {
          // A parcel switched off in the legend isn't there to click.
          if (object && look(idOf(object))) onPick(idOf(object));
        },
      });
    const out: Layer[] = [];
    const all = centres.data;
    if (dots && all) {
      const few =
        inView && fc ? inView.map((i) => fc.features[i]).filter((f): f is GeoJSON.Feature => !!f) : null;
      if (few) out.push(shapesLayer(few));
      else {
        const idx = all.flatMap((c, i) => (c ? [i] : []));
        out.push(
          new ScatterplotLayer<number>({
            id: "dots",
            data: idx,
            pickable: true,
            radiusUnits: "pixels",
            getRadius: 2.5,
            getPosition: (i) => all[i] as [number, number],
            getFillColor: (i) => look(i)?.fill ?? [0, 0, 0, 0],
            updateTriggers: { getFillColor: look },
            onClick: ({ object }) => {
              if (object != null && look(object)) onPick(object);
            },
          }),
        );
      }
    } else if (!dots && fc) out.push(shapesLayer(fc.features));
    const f = picked == null ? undefined : fc?.features[picked];
    if (f?.geometry)
      out.push(
        new GeoJsonLayer({
          id: "picked",
          data: { type: "FeatureCollection", features: [f] } as GeoJSON.FeatureCollection,
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
  }, [dots, centres.data, inView, fc, look, picked, onPick]);

  const ready = dots ? !!centres.data : !!fc;
  const failed = (dots ? centres.error : shapes.error)?.message;
  return (
    <div className="mg-map-body">
      {ready && (
        <MapView
          className="mg-mapview"
          label={g.mapLabel}
          layers={layers}
          bounds={bounds}
          fitKey={dots ? "centres" : "shapes"}
          resizeKey={mode}
          {...(dots ? { onMap: watch } : {})}
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
