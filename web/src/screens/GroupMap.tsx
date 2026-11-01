/** Model groups' map of the parcel shapes, coloured by group or by what moved, and the parcel inspector. */

import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer } from "@deck.gl/layers";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useMemo } from "react";
import { Button } from "react-aria-components";
import { api, type GroupsPreview, type ModelGroup, type ParcelInspect, unwrap } from "../api/client";
import { boundsOfGeoJson, MapView, rgba } from "../components/MapView";
import { Val } from "../components/Val";
import { short } from "../lib/format";
import { t } from "../strings";

const g = t.groups;

export type MapMode = "docked" | "full" | "hidden";
export type ColourBy = "group" | "changes";
export const CHANGE_GREY = "#d9dcd4";
export const SAME = "__same";

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
  const shapes = useQuery({
    queryKey: ["group-shapes", projectId],
    queryFn: async () => {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/groups/shapes`);
      if (!r.ok) throw new Error(await r.text());
      return (await r.json()) as GeoJSON.FeatureCollection;
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
  const fc = shapes.data;
  const bounds = useMemo(() => boundsOfGeoJson(fc), [fc]);

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
    if (!fc) return [];
    const idOf = (f: GeoJSON.Feature) => Number(f.id ?? -1);
    const out: Layer[] = [
      new GeoJsonLayer({
        id: "parcels",
        data: fc,
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
      }),
    ];
    const f = picked == null ? undefined : fc.features[picked];
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
    return out;
  }, [fc, look, picked, onPick]);

  return (
    <div className="mg-map-body">
      {fc && (
        <MapView
          className="mg-mapview"
          label={g.mapLabel}
          layers={layers}
          bounds={bounds}
          fitKey="shapes"
          resizeKey={mode}
        />
      )}
      {!shapes.data && <p className="mg-map-msg">{shapes.error?.message ?? g.loadingMap}</p>}
    </div>
  );
}

export function Inspector({
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
        <b className="mg-pop-title">{v ? g.parcel(short(v.key)) : "…"}</b>
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
                  <td className="mg-pop-v">
                    <Val v={f.value} />
                  </td>
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
