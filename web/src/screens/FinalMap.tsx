/** Model values' map: every parcel by its model value per finished area or its change from the roll, or each sale
 * the chosen set judges the values on, by its ratio. deck.gl draws them as dots, however many. */

import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, type FieldResult, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { Choice } from "../components/Form";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { Seg } from "../components/Seg";
import { t } from "../copy";
import { money, num, signed } from "../lib/format";
import { ratioColor, ratioStroke } from "./ValueMap";

type Receipt = components["schemas"]["FinalReceipt"];
type SetKey = Receipt["sets"][number]["key"];
type View = "ratio" | "value" | "change";
const mp = t.values.final.map;
const rm = t.ratio.map;

// Cheap to dear: ten steps, light to dark.
const SEQ = [
  "#fff5d6",
  "#fde3a7",
  "#fcc97c",
  "#f9a85c",
  "#f2844a",
  "#e2603f",
  "#c8413b",
  "#a32a3b",
  "#7a1d3a",
  "#4f1533",
];
const NONE: [number, number, number, number] = [150, 150, 150, 110];

type Parcels = components["schemas"]["ParcelPoints"];

/** A parcel's model value per finished area; null without either. */
function perArea(p: Parcels | undefined, i: number): number | null {
  const v = p?.value[i];
  const a = p?.area[i];
  return v != null && a != null && a > 0 ? v / a : null;
}

function deciles(xs: number[]): number[] {
  if (!xs.length) return [];
  const s = [...xs].sort((a, b) => a - b);
  return Array.from({ length: 9 }, (_, i) => s[Math.floor(((i + 1) / 10) * (s.length - 1))] ?? 0);
}

export function FinalMap({
  projectId,
  receipt,
  which,
  currency,
  units,
}: {
  projectId: string;
  receipt: Receipt;
  which: SetKey;
  currency: string;
  units: string;
}) {
  const [view, setView] = useState<View>("ratio");
  const [gid, setGid] = useState("");
  const unit = units === "imperial" ? "sq ft" : "m²";
  const names = Object.fromEntries(receipt.groups.map((g) => [g.id, g.name]));
  const parcels = useQuery({
    queryKey: ["final-parcels", projectId, receipt.ran_at],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/final/parcels", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled: view !== "ratio",
    staleTime: Number.POSITIVE_INFINITY,
  });
  const sales = useQuery({
    queryKey: ["final-sales", projectId, receipt.ran_at, which, gid],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/final/sales", {
          params: { path: { project_id: projectId }, query: { which, group: gid } },
        }),
      ),
    enabled: view === "ratio",
  });
  const p = parcels.data;
  // The parcels shown: of the group chosen, as indexes into the columns.
  const shown = useMemo(() => {
    if (!p) return [];
    const g = gid ? p.groups.indexOf(gid) : -1;
    const out: number[] = [];
    for (let i = 0; i < p.lon.length; i++) if (g < 0 || p.group[i] === g) out.push(i);
    return out;
  }, [p, gid]);
  const cuts = useMemo(
    () =>
      view === "value" ? deciles(shown.map((i) => perArea(p, i)).filter((x): x is number => x != null)) : [],
    [p, shown, view],
  );
  const s = sales.data;
  const layers = useMemo(() => {
    if (view === "ratio")
      return s
        ? [
            new ScatterplotLayer({
              id: "sales",
              data: s,
              getPosition: (x) => [x.lon, x.lat],
              getRadius: (x) => (x.trimmed ? 3 : 4.5),
              radiusUnits: "pixels",
              getFillColor: (x) => (x.trimmed ? rgba("#d0d0d0", 0.85) : rgba(ratioColor(x.ratio), 0.85)),
              getLineColor: (x) => (x.trimmed ? rgba("#9a9a9a") : rgba(ratioStroke(x.ratio))),
              stroked: true,
              lineWidthUnits: "pixels",
              getLineWidth: 0.85,
              pickable: true,
            }),
          ]
        : [];
    if (!p) return [];
    const colour = (i: number): [number, number, number, number] => {
      const v = p.value[i];
      if (v == null) return NONE;
      if (view === "change") {
        const r = p.roll[i];
        return r != null && r > 0 ? rgba(ratioColor(v / r), 0.85) : NONE;
      }
      const x = perArea(p, i);
      if (x == null) return NONE;
      let k = 0;
      while (k < cuts.length && x > (cuts[k] ?? 0)) k++;
      return rgba(SEQ[k] ?? "#4f1533", 0.85);
    };
    return [
      new ScatterplotLayer<number>({
        id: `parcels-${view}`,
        data: shown,
        getPosition: (i) => [p.lon[i] ?? 0, p.lat[i] ?? 0],
        getRadius: 2.5,
        radiusUnits: "pixels",
        radiusMinPixels: 1.5,
        getFillColor: colour,
        pickable: true,
        updateTriggers: { getFillColor: [view, cuts] },
      }),
    ];
  }, [view, s, p, shown, cuts]);

  const bounds = useMemo(
    () =>
      view === "ratio"
        ? boundsOf((s ?? []).map((x) => [x.lon, x.lat] as const))
        : p
          ? boundsOf(shown.map((i) => [p.lon[i] ?? Number.NaN, p.lat[i] ?? Number.NaN] as const))
          : null,
    [view, s, p, shown],
  );
  const fmt = (v: number | null | undefined) => (v == null ? mp.tip.noValue : money(v, currency));
  const tooltip = ({ object, index }: { object?: unknown; index: number }) => {
    if (view === "ratio") {
      const x = object as FieldResult["trimmed"][number] | undefined;
      return x
        ? `${rm.ratio} ${num(x.ratio, 3)} · ${rm.price} ${fmt(x.price)} · ${rm.value} ${fmt(x.value)}`
        : null;
    }
    const i = shown[index];
    if (!p || i == null) return null;
    const v = p.value[i];
    const r = p.roll[i];
    const pa = perArea(p, i);
    return [
      `${mp.tip.group} ${names[p.groups[p.group[i] ?? 0] ?? ""] ?? ""}`,
      `${mp.tip.value} ${fmt(v)}`,
      ...(r != null ? [`${mp.tip.roll} ${fmt(r)}`] : []),
      ...(v != null && r != null && r > 0 ? [`${mp.tip.change} ${signed(100 * (v / r - 1), 1)}%`] : []),
      ...(pa != null ? [`${mp.tip.perArea({ unit })} ${money(pa, currency)}`] : []),
    ].join("\n");
  };
  const valuedGroups = receipt.groups.filter((g) => g.valued > 0);
  const loading = view === "ratio" ? sales.isLoading : parcels.isLoading;
  const error = (view === "ratio" ? sales.error : parcels.error)?.message;
  const empty = view === "ratio" ? s && s.length === 0 : p && shown.length === 0;

  return (
    <div className="fv-map">
      <div className="fv-on">
        <span className="mo-label">{mp.show}</span>
        <Seg
          label={mp.show}
          value={view}
          options={(["ratio", "value", "change"] as const).map((k) => [k, mp.views[k] ?? k] as const)}
          onChange={setView}
          disabled={receipt.roll ? [] : ["change"]}
        />
        <Choice
          label={mp.all}
          hideLabel
          value={gid}
          options={[
            ["", mp.all] as [string, string],
            ...valuedGroups.map((g) => [g.id, g.name] as [string, string]),
          ]}
          onChange={setGid}
        />
      </div>
      <p className="wiz-from">{mp.why[view]}</p>
      {error ? (
        <p className="error">{error}</p>
      ) : empty ? (
        <p className="wiz-from">{mp.none}</p>
      ) : (
        <MapView
          className="rv-map"
          label={mp.label}
          layers={layers}
          bounds={bounds}
          fitKey={`${view === "ratio" ? "s" : "p"}:${gid}:${loading ? 0 : 1}`}
          tooltip={tooltip}
        >
          {loading && <p className="mg-map-msg">{mp.loading}</p>}
        </MapView>
      )}
      <div className="rv-legend">
        {view === "value"
          ? SEQ.map((c, k) => (
              <span key={c}>
                <span className="rv-swatch" style={{ background: c, borderColor: c }} />
                {k === 0
                  ? `≤ ${money(cuts[0] ?? 0, currency)}`
                  : k === SEQ.length - 1
                    ? `> ${money(cuts[k - 1] ?? 0, currency)}`
                    : k % 3 === 0
                      ? money(cuts[k] ?? 0, currency)
                      : ""}
              </span>
            ))
          : (view === "ratio" ? rm.legend : mp.changeLegend).map(([q, label]) => (
              <span key={label}>
                <span
                  className="rv-swatch"
                  style={{ background: ratioColor(q), borderColor: ratioStroke(q) }}
                />
                {label}
              </span>
            ))}
        {view !== "ratio" && (
          <span>
            <span className="rv-swatch" style={{ background: "#969696", borderColor: "#969696" }} />
            {mp.unvalued}
          </span>
        )}
        {view === "ratio" && (
          <span>
            <span className="rv-swatch" style={{ background: "#d0d0d0", borderColor: "#9a9a9a" }} />
            {rm.trimmed}
          </span>
        )}
      </div>
    </div>
  );
}
