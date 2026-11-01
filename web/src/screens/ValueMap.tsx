/** Check my values' map of each sale's ratio, and the median ratio by its region's price level. */

import { ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, type FieldResult, type RatioSetup, unwrap } from "../api/client";
import { Choice } from "../components/Form";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { money, num, ratioText, signed } from "../lib/format";
import { t } from "../strings";
import { BandChart } from "./ValueCharts";

const r = t.ratio;

/** openratiostudy.com's colours: blue below 1 (deepest at 0.5), white at 1, red above (deepest at 2). */
export function ratioColor(q: number): string {
  if (!Number.isFinite(q)) return "#94a3b8";
  if (q <= 1) {
    const c = Math.round(255 * Math.max(0, Math.min(1, (q - 0.5) / 0.5)));
    return `rgb(${c}, ${c}, 255)`;
  }
  const c = Math.round(255 * (1 - Math.max(0, Math.min(1, q - 1))));
  return `rgb(255, ${c}, ${c})`;
}

export function ratioStroke(q: number): string {
  return q < 0.9 ? "#1d4ed8" : q > 1.1 ? "#b91c1c" : "#475569";
}

/** Each sale on the map, coloured by its ratio: clusters of high or low ratios show where values are off. */
export function RatioMap({
  projectId,
  result,
  currency,
}: {
  projectId: string;
  result: FieldResult;
  currency: string;
}) {
  const studied = result.groups.filter((g) => g.sales > 0);
  const [gid, setGid] = useState("");
  const pts = useQuery({
    queryKey: ["ratio-map", projectId, result.field, gid],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/map", {
          params: { path: { project_id: projectId }, query: { field: result.field, group: gid } },
        }),
      ),
  });
  const data = pts.data;
  const layers = useMemo(
    () =>
      data
        ? [
            new ScatterplotLayer({
              id: "sales",
              data,
              getPosition: (p) => [p.lon, p.lat],
              getRadius: (p) => (p.trimmed ? 3 : 4.5),
              radiusUnits: "pixels",
              getFillColor: (p) => (p.trimmed ? rgba("#d0d0d0", 0.85) : rgba(ratioColor(p.ratio), 0.85)),
              getLineColor: (p) => (p.trimmed ? rgba("#9a9a9a") : rgba(ratioStroke(p.ratio))),
              stroked: true,
              lineWidthUnits: "pixels",
              getLineWidth: 0.85,
              pickable: true,
            }),
          ]
        : [],
    [data],
  );
  const fmt = (v: number) => money(v, currency);
  const mp = r.map;
  return (
    <div className="rv-cards">
      <div className="cs-row">
        <Choice
          label={r.table.group}
          hideLabel
          value={gid}
          options={[
            ["", result.overall.name] as [string, string],
            ...studied.map((x) => [x.id, x.name] as [string, string]),
          ]}
          onChange={setGid}
        />
        <span className="wiz-from">{mp.lede}</span>
      </div>
      {pts.data && pts.data.length === 0 ? (
        <p className="wiz-from">{mp.none}</p>
      ) : (
        <MapView
          className="rv-map"
          label={mp.label}
          layers={layers}
          bounds={data ? boundsOf(data.map((p) => [p.lon, p.lat] as const)) : null}
          fitKey={`${gid}:${data?.length ?? 0}`}
          tooltip={({ object: p }) =>
            p
              ? `${mp.ratio} ${num(p.ratio, 3)} · ${mp.price} ${fmt(p.price)} · ${mp.value} ${fmt(p.value)}${p.trimmed ? ` · ${mp.trimmed}` : ""}`
              : null
          }
        />
      )}
      <div className="rv-legend">
        {mp.legend.map(([q, label]) => (
          <span key={label}>
            <span className="rv-swatch" style={{ background: ratioColor(q), borderColor: ratioStroke(q) }} />
            {label}
          </span>
        ))}
        <span>
          <span className="rv-swatch" style={{ background: "#d0d0d0", borderColor: "#9a9a9a" }} />
          {mp.trimmed}
        </span>
      </div>
    </div>
  );
}

/** The median ratio by the price level of the region each sale is in (openratiostudy.com's neighbourhood price
 * levels): it tells real vertical inequity from invalid sales at low prices in dear areas. */
export function Regions({
  result,
  setup,
  currency,
  choose,
  busy,
}: {
  result: FieldResult;
  setup: RatioSetup | undefined;
  currency: string;
  choose: (region: string) => void;
  busy: boolean;
}) {
  const studied = result.groups.filter((g) => g.sales > 0);
  const [gid, setGid] = useState("");
  const g = result.groups.find((x) => x.id === gid) ?? result.overall;
  const rg = g.regions;
  const rr = r.regions;
  return (
    <div className="rv-cards">
      <p className="wiz-lede">{rr.lede}</p>
      <div className="cs-row">
        {setup && (
          <Choice
            label={rr.field}
            value={setup.region}
            isDisabled={busy}
            options={[
              ["", rr.noField] as [string, string],
              ...setup.regions.map((x) => [x.value, x.label] as [string, string]),
            ]}
            onChange={choose}
          />
        )}
        <Choice
          label={r.table.group}
          value={gid}
          options={[
            ["", result.overall.name] as [string, string],
            ...studied.map((x) => [x.id, x.name] as [string, string]),
          ]}
          onChange={setGid}
        />
      </div>
      {!rg ? (
        <p className="wiz-from">
          {setup?.region ? rr.notRun : setup && setup.regions.length === 0 ? rr.noLocations : rr.choose}
        </p>
      ) : rg.strata.length < 2 ? (
        <p className="wiz-from">{rr.few(rg.sales, rg.regions)}</p>
      ) : (
        <>
          <p>
            {rr.reading(
              rg.regions,
              rg.sales,
              rg.vei == null ? "—" : `${signed(rg.vei, 1)}%`,
              r.table.verdicts[rg.vei_verdict] ?? rg.vei_verdict,
            )}
          </p>
          <BandChart
            series={[
              { label: rr.byLevel, color: "#2f5d9b", bands: rg.strata },
              ...(g.strata.length ? [{ label: rr.bySale, color: "#d4566f", bands: g.strata }] : []),
            ]}
          />
          <table className="tbl">
            <thead>
              <tr>
                <th>{rr.group}</th>
                <th className="cs-n">{rr.regionsCol}</th>
                <th className="cs-n">{r.table.sales}</th>
                <th className="cs-n">{rr.level}</th>
                <th className="cs-n">{r.table.median}</th>
                <th className="cs-n">{r.table.range}</th>
              </tr>
            </thead>
            <tbody>
              {rg.strata.map((x, k) => (
                <tr key={`${x.level}-${x.n}-${x.median}`}>
                  <td>{k === 0 ? rr.lowest : k === rg.strata.length - 1 ? rr.highest : k + 1}</td>
                  <td className="cs-n">{num(x.regions)}</td>
                  <td className="cs-n">{num(x.n)}</td>
                  <td className="cs-n">{money(x.level, currency)}</td>
                  <td className="cs-n">{ratioText(x.median)}</td>
                  <td className="cs-n">
                    {ratioText(x.low)} to {ratioText(x.high)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="wiz-from">{rr.compare(g.vei == null ? "—" : `${signed(g.vei, 1)}%`)}</p>
        </>
      )}
    </div>
  );
}
