/** Model groups' map of the parcel shapes, coloured by group or by what moved, and the parcel inspector. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "react-aria-components";
import { api, type GroupsPreview, type ModelGroup, type ParcelInspect, unwrap } from "../api/client";
import { addBasemap } from "../components/basemap";
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
  useEffect(() => {
    pick.current = onPick;
  });

  useEffect(() => {
    if (!el.current || !shapes.data) return;
    const m = L.map(el.current, { preferCanvas: true, zoomSnap: 0.25 });
    addBasemap(m);
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
      const unchanged = colourBy === "changes" && a === (saved?.[i] ?? -1);
      if (unchanged) fill = CHANGE_GREY;
      // Switched off in the legend: not drawn, and not clickable (canvas hits need a fill or a stroke).
      const key = unchanged ? SAME : a >= 0 ? (ids[a] ?? "") : "";
      if (hidden.has(key)) return { fill: false, stroke: false };
      const dim = hl && !hl.has(i);
      return {
        fill: true,
        stroke: true,
        fillColor: fill,
        fillOpacity: dim ? 0.18 : 0.72,
        color: hl?.has(i) ? "#111" : "#ffffff",
        weight: hl?.has(i) ? 1.4 : 0.4,
        opacity: dim ? 0.3 : 0.9,
      };
    };
    layer.current?.setStyle((f) => style.current(Number(f?.id ?? -1)));
  }, [preview, colours, ids, hidden, unassigned, colourBy, highlight, shapes.data]);

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
