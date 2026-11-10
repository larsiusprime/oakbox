/** Sales set aside, in the map window (SPEC §3.15, a take-over step): each one where it is, coloured by the check
 * that flagged it (decided ones faint), the picked one ringed with the sales it was compared with; a dot clicked
 * picks that sale in the list. Picking one moves the map to it and its comps. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { OUTLIER, SALE } from "../lib/colours";
import { t } from "../wording";

type Point = components["schemas"]["ReviewPoint"];
const s = t.sales.review;

// One colour a check (the first that flagged a sale), in the order the checks are listed.
const CHECK_COLOURS = [
  "#d4566f",
  "#e8955a",
  "#c9a227",
  "#5fa55a",
  "#3a8fb7",
  "#7a5fb0",
  "#b0607a",
  "#6d8b74",
  "#8c6d46",
];
const CHECKS = Object.keys(t.sales.review.checkNames);
const colourOf = (check: string | undefined) =>
  CHECK_COLOURS[Math.max(0, CHECKS.indexOf(check ?? "")) % CHECK_COLOURS.length] ?? "#888888";

export function ReviewMap({
  projectId,
  points,
  picked,
  pick,
}: {
  projectId: string;
  points: Point[];
  picked: string | null;
  pick: (key: string) => void;
}) {
  const detail = useQuery({
    queryKey: ["clean-sale", projectId, picked],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: picked ?? "" } },
        }),
      ),
    enabled: !!picked,
  });
  const members = (detail.data?.members ?? []).filter(
    (m) => m.latitude != null && m.longitude != null && m.key_sale !== picked,
  );
  const me = points.find((p) => p.key_sale === picked);
  const layers = useMemo(
    () => [
      new ScatterplotLayer<Point>({
        id: "aside",
        data: points,
        pickable: true,
        radiusUnits: "pixels",
        getRadius: 5,
        getPosition: (p) => [p.longitude, p.latitude],
        getFillColor: (p) => rgba(colourOf(p.checks[0]), p.status === "undecided" ? 0.9 : 0.35),
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 0.75,
        getLineColor: [255, 255, 255, 220],
        onClick: ({ object }) => {
          if (object) pick((object as Point).key_sale);
        },
      }),
      new ScatterplotLayer({
        id: "comps",
        data: members,
        radiusUnits: "pixels",
        getRadius: 7,
        filled: false,
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 2,
        getPosition: (m: (typeof members)[number]) => [m.longitude ?? 0, m.latitude ?? 0],
        getLineColor: rgba(OUTLIER.comp),
      }),
      ...(me
        ? [
            new ScatterplotLayer<Point>({
              id: "picked",
              data: [me],
              radiusUnits: "pixels",
              getRadius: 9,
              getPosition: (p) => [p.longitude, p.latitude],
              getFillColor: rgba(SALE.self),
              stroked: true,
              lineWidthUnits: "pixels",
              getLineWidth: 3,
              getLineColor: rgba(OUTLIER.ring),
            }),
          ]
        : []),
    ],
    [points, members, me, pick],
  );
  // Picked: the map goes to it and its comps; else every sale set aside.
  const around = me
    ? boundsOf([
        [me.longitude, me.latitude] as const,
        ...members.map((m) => [m.longitude ?? 0, m.latitude ?? 0] as const),
      ])
    : boundsOf(points.map((p) => [p.longitude, p.latitude] as const));
  const shown = [...new Set(points.map((p) => p.checks[0] ?? ""))].filter((c) => c in s.checkNames);
  return (
    <div className="mapwin-body">
      <div className="mapwin-stage">
        <MapView
          className="mapwin-map"
          label={s.mapLabel}
          layers={layers}
          bounds={around}
          fitKey={`${picked ?? ""}:${members.length}:${points.length}`}
          tooltip={({ object }) =>
            object && "checks" in (object as Point)
              ? (object as Point).checks
                  .map((c) => s.checkNames[c as keyof typeof s.checkNames] ?? c)
                  .join(", ")
              : null
          }
          cursor={({ object }) => (object ? "pointer" : "")}
        />
      </div>
      <div className="rv-legend mapwin-legend-row">
        {shown.map((c) => (
          <span key={c}>
            <span className="rv-swatch" style={{ background: colourOf(c) }} />
            {s.checkNames[c as keyof typeof s.checkNames]}
          </span>
        ))}
        <span>
          <span className="rv-swatch ol-ring" />
          {s.mapComps}
        </span>
        <span className="wiz-from">{s.mapFaint}</span>
      </div>
    </div>
  );
}
