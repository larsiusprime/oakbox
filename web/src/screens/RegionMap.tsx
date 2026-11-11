/** Neighbourhood price levels in the map window (SPEC §3.15, a take-over step): each sale studied, coloured by its
 * neighbourhood's median ratio (the outlying ratios left out of it), for the model group picked on the page. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { ratioColor, ratioStroke, TRIMMED } from "../lib/colours";
import { num, ratioText } from "../lib/format";
import { t } from "../wording";

const rr = t.ratio.regions;
type Dot = { lon: number; lat: number; region: number };

export function RegionMap({
  projectId,
  field,
  region,
  group,
}: {
  projectId: string;
  field: string;
  region: string;
  group: string;
}) {
  const q = useQuery({
    queryKey: ["ratio-regions", projectId, field, region, group],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/regions", {
          params: { path: { project_id: projectId }, query: { field, region, group } },
        }),
      ),
  });
  const d = q.data;
  const dots: Dot[] = d ? d.lon.map((lon, i) => ({ lon, lat: d.lat[i] ?? 0, region: d.region[i] ?? 0 })) : [];
  // Against the median of them all: the page asks whether some neighbourhoods are valued apart from the rest, not
  // whether all are under; a quarter under the rest is as deep as the colours go.
  const overall = d?.overall ?? null;
  const median = (k: number) => d?.median[k] ?? null;
  const shade = (k: number) => {
    const m = median(k);
    return m == null || !overall ? null : 1 + 2 * (m / overall - 1);
  };
  const layers = [
    new ScatterplotLayer<Dot>({
      id: "regions",
      data: dots,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 5,
      getPosition: (p) => [p.lon, p.lat],
      getFillColor: (p) => {
        const q = shade(p.region);
        return q == null ? rgba(TRIMMED.fill) : rgba(ratioColor(q));
      },
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      getLineColor: (p) => {
        const q = shade(p.region);
        return q == null ? rgba(TRIMMED.fill) : rgba(ratioStroke(q));
      },
    }),
  ];
  return (
    <div className="mapwin-body">
      <div className="mapwin-stage">
        <MapView
          className="mapwin-map"
          label={rr.mapLabel}
          layers={layers}
          bounds={boundsOf(dots.map((p) => [p.lon, p.lat] as const))}
          fitKey={`${group}:${region}:${dots.length}`}
          tooltip={({ object }) => {
            const p = object as Dot | null;
            if (!p || !d || !("region" in p)) return null;
            const m = median(p.region);
            return rr.mapTip({
              region: d.regions[p.region] ?? "",
              median: m == null ? "—" : ratioText(m),
              n: num(d.sales[p.region] ?? 0),
            });
          }}
        />
      </div>
      <div className="rv-legend mapwin-legend-row">
        {d && (
          <span>
            <b>
              {rr.mapOf({
                regions: num(d.regions.length),
                sales: num(dots.length),
                median: overall == null ? "—" : ratioText(overall),
              })}
            </b>
          </span>
        )}
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(0.7) }} />
          {rr.mapLow}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: ratioColor(1.4) }} />
          {rr.mapHigh}
        </span>
      </div>
    </div>
  );
}
