/** Extreme ratios in the map window (SPEC §3.15, a take-over step): every sale studied, faint, coloured by its ratio;
 * the extreme ones (trimmed) drawn bold; the one picked (its row's Show on map, or clicked on the map) ringed and the
 * map moved to it. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { api, type FieldResult, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { OUTLIER, ratioColor, ratioStroke, TRIMMED } from "../lib/colours";
import { num } from "../lib/format";
import { t } from "../wording";

type Point = components["schemas"]["MapPoint"];
const e = t.ratio.extreme;

export function ExtremeMap({
  projectId,
  result,
  picked,
  pick,
}: {
  projectId: string;
  result: FieldResult;
  picked: string;
  pick: (key: string) => void;
}) {
  const q = useQuery({
    queryKey: ["ratio-map", projectId, result.field, ""],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/map", {
          params: { path: { project_id: projectId }, query: { field: result.field, group: "" } },
        }),
      ),
  });
  const all = q.data ?? [];
  const extreme = new Set(result.trimmed.map((x) => x.key_sale));
  const me = all.find((p) => p.key_sale === picked && extreme.has(picked));
  // Worked out as it draws: the React Compiler keeps it while nothing it reads changes.
  const layers = [
    new ScatterplotLayer<Point>({
      id: "studied",
      data: all.filter((p) => !extreme.has(p.key_sale ?? "")),
      radiusUnits: "pixels",
      getRadius: 3,
      getPosition: (p) => [p.lon, p.lat],
      getFillColor: (p) => rgba(ratioColor(p.ratio), 0.35),
    }),
    new ScatterplotLayer<Point>({
      id: "extreme",
      data: all.filter((p) => extreme.has(p.key_sale ?? "")),
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 6,
      getPosition: (p) => [p.lon, p.lat],
      getFillColor: (p) => rgba(ratioColor(p.ratio)),
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      getLineColor: (p) => rgba(ratioStroke(p.ratio)),
      onClick: ({ object }) => {
        if (object?.key_sale) pick(object.key_sale);
      },
    }),
    ...(me
      ? [
          new ScatterplotLayer<Point>({
            id: "picked",
            data: [me],
            radiusUnits: "pixels",
            getRadius: 11,
            filled: false,
            stroked: true,
            lineWidthUnits: "pixels",
            getLineWidth: 3,
            getPosition: (p) => [p.lon, p.lat],
            getLineColor: rgba(OUTLIER.ring),
          }),
        ]
      : []),
  ];
  // Picked: the map goes to it (a little around it); else every extreme sale.
  const shown = all.filter((p) => extreme.has(p.key_sale ?? ""));
  const pad = 0.004;
  const bounds = me
    ? boundsOf([
        [me.lon - pad, me.lat - pad],
        [me.lon + pad, me.lat + pad],
      ])
    : boundsOf((shown.length ? shown : all).map((p) => [p.lon, p.lat] as const));
  return (
    <div className="mapwin-body">
      <div className="mapwin-stage">
        <MapView
          className="mapwin-map"
          label={e.mapLabel}
          layers={layers}
          bounds={bounds}
          fitKey={`${me?.key_sale ?? ""}:${all.length}`}
          tooltip={({ object }) =>
            object && "ratio" in (object as Point) ? `${e.ratio} ${num((object as Point).ratio, 2)}` : null
          }
          cursor={({ object }) => (object ? "pointer" : "")}
        />
      </div>
      <div className="rv-legend mapwin-legend-row">
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(0.5) }} />
          {e.mapLow}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(2) }} />
          {e.mapHigh}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: TRIMMED.fill }} />
          {e.mapRest}
        </span>
      </div>
    </div>
  );
}
