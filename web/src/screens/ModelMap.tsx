/** How they did in the map window (SPEC §3.15, a take-over step): the model group's held-out sales, each coloured by
 * one model's ratio (its value over the price); the model is the one whose row's Map was pressed, the ensemble at
 * first. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { ShowOnMap } from "../components/ShowOnMap";
import { ratioColor, ratioStroke } from "../lib/colours";
import { num } from "../lib/format";
import { useMapStep } from "../lib/mapstep";
import { t } from "../wording";

type Point = components["schemas"]["MapPoint"];
const h = t.values.model.how;

/** The model and set of sales on the map: the row's Map pressed (set|model), else the ensemble on the holdout. */
export function useMapModel(): { set: string; model: string } {
  const pick = useMapStep()?.pick ?? "";
  const [set, model] = pick.includes("|") ? pick.split("|", 2) : ["holdout", pick || "ensemble"];
  return { set: set || "holdout", model: model || "ensemble" };
}

/** Map on a model's row in a set's table: that model's ratios on that set's sales. */
export function ModelOnMap({ set, model }: { set: string; model: string }) {
  const on = useMapModel();
  const shown = on.set === set && on.model === model;
  return (
    <span title={shown ? h.onMapTip : h.mapItTip}>
      <ShowOnMap id={`${set}|${model}`} shown={shown} label={shown ? h.onMapTip : h.mapItTip} compact />
    </span>
  );
}

export function ModelMap({
  projectId,
  group,
  groupName,
  model,
  modelName,
  set,
}: {
  projectId: string;
  group: string;
  groupName: string;
  model: string;
  modelName: string;
  /** The set of sales: the holdout (held-out predictions), or another set by its dates. */
  set: { key: string; name: string; first: string | null; last: string | null };
}) {
  const heldOut = set.key === "holdout";
  const q = useQuery({
    queryKey: ["model-sales", projectId, group, model, set.key, set.first, set.last],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/model/sales", {
          params: {
            path: { project_id: projectId },
            query: heldOut
              ? { group, model }
              : { group, model, first: set.first ?? "", last: set.last ?? "", held_out: false },
          },
        }),
      ),
  });
  const all = q.data ?? [];
  const layers = [
    new ScatterplotLayer<Point>({
      id: "held-out",
      data: all,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 5,
      getPosition: (p) => [p.lon, p.lat],
      getFillColor: (p) => rgba(ratioColor(p.ratio)),
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      getLineColor: (p) => rgba(ratioStroke(p.ratio)),
    }),
  ];
  return (
    <div className="mapwin-body">
      <div className="mapwin-stage">
        <MapView
          className="mapwin-map"
          label={h.mapLabel}
          layers={layers}
          bounds={boundsOf(all.map((p) => [p.lon, p.lat] as const))}
          fitKey={`${group}:${all.length}`}
          tooltip={({ object }) => {
            const p = object as Point | null;
            return p && "ratio" in p
              ? h.mapTip({ ratio: num(p.ratio, 2), price: num(p.price), value: num(p.value) })
              : null;
          }}
        />
      </div>
      <div className="rv-legend mapwin-legend-row">
        <span>
          <b>
            {q.isSuccess && !all.length
              ? h.mapNone
              : h.mapOf({ model: modelName, group: groupName, n: num(all.length), set: set.name })}
          </b>
        </span>
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(0.7) }} />
          {h.mapLow}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(1.4) }} />
          {h.mapHigh}
        </span>
      </div>
    </div>
  );
}
