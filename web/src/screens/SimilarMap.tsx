/** Similar parcels in the map window (SPEC §3.15, a take-over step): every parcel coloured by how far apart its group
 * of similar parcels' values are (the CHD): green alike, amber some spread, red far apart; grey a group of one. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { FieldResult } from "../api/client";
import { api, unwrap } from "../api/client";
import { Choice } from "../components/Form";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { num } from "../lib/format";
import { t } from "../wording";

const sm = t.ratio.similar;
// The same bands as the table's reading: under 20 alike, under 40 some spread, else far apart.
const TIGHT = "#5fa55a";
const SOME = "#e0a33a";
const WIDE = "#c8453b";
const ONE = "#b5b5b5";
const colourOf = (c: number | null | undefined) => (c == null ? ONE : c < 20 ? TIGHT : c < 40 ? SOME : WIDE);

export function SimilarMap({
  projectId,
  result,
  group,
  setGroup,
}: {
  projectId: string;
  result: FieldResult;
  group: string;
  setGroup: (id: string) => void;
}) {
  const q = useQuery({
    queryKey: ["ratio-similar", projectId, result.field, group],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/similar", {
          params: { path: { project_id: projectId }, query: { field: result.field, group } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const d = q.data;
  const idx = useMemo(() => (d ? d.lon.map((_, i) => i) : []), [d]);
  const layers = useMemo(
    () =>
      d
        ? [
            new ScatterplotLayer<number>({
              id: "similar",
              data: idx,
              pickable: true,
              radiusUnits: "pixels",
              getRadius: 2.5,
              getPosition: (i) => [d.lon[i] ?? 0, d.lat[i] ?? 0],
              getFillColor: (i) => rgba(colourOf(d.chd[i]), 0.85),
            }),
          ]
        : [],
    [d, idx],
  );
  const studied = result.groups.filter((g) => (g.parcels ?? 0) > 0);
  return (
    <div className="mapwin-body">
      <div className="mapwin-sub">
        <Choice
          label={t.ratio.table.group}
          hideLabel
          value={group}
          options={[
            ["", result.overall.name] as [string, string],
            ...studied.map((x) => [x.id, x.name] as [string, string]),
          ]}
          onChange={setGroup}
        />
      </div>
      <div className="mapwin-stage">
        <MapView
          className="mapwin-map"
          label={sm.mapLabel}
          layers={layers}
          bounds={d ? boundsOf(idx.map((i) => [d.lon[i] ?? 0, d.lat[i] ?? 0] as const)) : null}
          fitKey={`${group}:${d?.lon.length ?? 0}`}
          tooltip={({ index }) =>
            d && index >= 0
              ? d.chd[index] == null
                ? sm.mapOne
                : sm.mapTip({ chd: num(d.chd[index] ?? 0, 1), n: d.size[index] ?? 0 })
              : null
          }
        />
      </div>
      <div className="rv-legend mapwin-legend-row">
        <span>
          <span className="rv-swatch" style={{ background: TIGHT }} />
          {sm.tight}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: SOME }} />
          {sm.some}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: WIDE }} />
          {sm.wide}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: ONE }} />
          {sm.mapOneShort}
        </span>
      </div>
    </div>
  );
}
