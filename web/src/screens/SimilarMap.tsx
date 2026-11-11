/** Similar parcels in the map window (SPEC §3.15, a take-over step): every parcel coloured by how far apart its group
 * of similar parcels' values are (the CHD): green alike, amber some spread, red far apart; grey a group of one. */
import { ScatterplotLayer } from "@deck.gl/layers";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { FieldResult } from "../api/client";
import { api, unwrap } from "../api/client";
import { CloseButton } from "../components/Buttons";
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
  // A parcel clicked: its group of similar parcels in a card, every one ringed; one of them picked from the card.
  const [picked, setPicked] = useState<{ cluster: string; key: string | null } | null>(null);
  const g = useQuery({
    queryKey: ["ratio-similar-group", projectId, result.field, picked?.cluster],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/similar/group", {
          params: {
            path: { project_id: projectId },
            query: { field: result.field, cluster: picked?.cluster ?? "" },
          },
        }),
      ),
    enabled: !!picked,
  });
  const members = picked && g.data?.cluster === picked.cluster ? g.data.members : [];
  const me = members.find((m) => m.key === picked?.key) ?? null;
  type Member = (typeof members)[number];
  const layers = d
    ? [
        new ScatterplotLayer<number>({
          id: "similar",
          data: idx,
          pickable: true,
          radiusUnits: "pixels",
          getRadius: 2.5,
          getPosition: (i) => [d.lon[i] ?? 0, d.lat[i] ?? 0],
          getFillColor: (i) => rgba(colourOf(d.chd[i]), picked ? 0.35 : 0.85),
          updateTriggers: { getFillColor: !!picked },
          onClick: ({ index }) => {
            const c = index >= 0 ? d.clusters[d.cluster[index] ?? -1] : undefined;
            if (c) setPicked({ cluster: c, key: null });
          },
        }),
        new ScatterplotLayer<Member>({
          id: "group",
          data: members,
          radiusUnits: "pixels",
          getRadius: 6,
          filled: true,
          getFillColor: rgba(colourOf(g.data?.chd), 0.9),
          stroked: true,
          lineWidthUnits: "pixels",
          getLineWidth: 1.5,
          getLineColor: [30, 30, 30, 230],
          getPosition: (m) => [m.lon, m.lat],
        }),
        ...(me
          ? [
              new ScatterplotLayer<Member>({
                id: "picked",
                data: [me],
                radiusUnits: "pixels",
                getRadius: 11,
                filled: false,
                stroked: true,
                lineWidthUnits: "pixels",
                getLineWidth: 3,
                getLineColor: [17, 17, 17, 255],
                getPosition: (m) => [m.lon, m.lat],
              }),
            ]
          : []),
      ]
    : [];
  const pad = 0.002;
  const bounds = me
    ? boundsOf([
        [me.lon - pad, me.lat - pad],
        [me.lon + pad, me.lat + pad],
      ])
    : members.length
      ? boundsOf(members.map((m) => [m.lon, m.lat] as const))
      : d
        ? boundsOf(idx.map((i) => [d.lon[i] ?? 0, d.lat[i] ?? 0] as const))
        : null;
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
          bounds={bounds}
          fitKey={`${group}:${d?.lon.length ?? 0}:${picked?.cluster ?? ""}:${members.length}:${picked?.key ?? ""}`}
          cursor={({ object }) => (object !== undefined && object !== null ? "pointer" : "")}
          tooltip={({ index }) =>
            d && index >= 0
              ? d.chd[index] == null
                ? sm.mapOne
                : `${sm.mapTip({ chd: num(d.chd[index] ?? 0, 1), n: d.size[index] ?? 0 })} · ${sm.mapClick}`
              : null
          }
        />
        {picked && g.data && (
          <section className="sim-card" aria-label={sm.cardTitle({ n: members.length })}>
            <header>
              <b>{sm.cardTitle({ n: members.length })}</b>
              <CloseButton label={sm.cardClose} onPress={() => setPicked(null)} />
            </header>
            <p className="sim-figs">
              {sm.cardFigures({
                median: g.data.median == null ? "—" : num(g.data.median),
                chd: g.data.chd == null ? "—" : num(g.data.chd, 1),
              })}
            </p>
            <p className="sim-hint">{sm.cardHint}</p>
            <ol className="sim-list">
              {members.map((m) => (
                <li key={m.key} className={m.key === picked.key ? "on" : ""}>
                  <button
                    type="button"
                    className="wiz-link mono"
                    aria-current={m.key === picked.key ? "true" : undefined}
                    onClick={() => setPicked({ cluster: picked.cluster, key: m.key })}
                  >
                    {m.key}
                  </button>
                  <span className="sim-val">{m.value == null ? sm.cardBlank : num(m.value)}</span>
                </li>
              ))}
            </ol>
          </section>
        )}
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
