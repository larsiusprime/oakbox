/** 6. Models › Outliers (SPEC F9, slice 3): the sales the models valued furthest from their price, on a map and in a
 * list; one picked: its comps and how it's unlike the others; why it's off (the sale, the data, the group, the
 * model); what the misses have in common; the patches made. */

import { ScatterplotLayer } from "@deck.gl/layers";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useMemo, useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { type StepId, stepChanged } from "../api/steps";
import { Choice, Field } from "../components/Form";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { Seg } from "../components/Seg";
import { day, money, num, pct } from "../lib/format";
import { t } from "../wording";

type S = components["schemas"];
type Why = S["OutlierCallBody"]["why"];
type Reason = NonNullable<S["OutlierCallBody"]["reason"]>;
const o = t.values.outliers;
const LOW = "#c2410c";
const HIGH = "#1d4ed8";
const WITHIN = "#9ca3af";
const WHYS: Why[] = ["invalid", "data", "group", "model"];
const REASONS: Reason[] = [
  "related",
  "multi_parcel",
  "partial",
  "wrong_price",
  "distressed",
  "changed",
  "not_open_market",
  "other",
];
// The step a call puts out of date first (the steps after it follow).
const FROM: Record<Why, StepId | null> = {
  invalid: "clean",
  data: "bring-in",
  group: "assemble",
  model: null,
};

export function Outliers({ projectId, currency }: { projectId: string; currency: string }) {
  const [group, setGroup] = useState<string | null>(null);
  const [which, setWhich] = useState<"all" | "low" | "high">("all");
  const [state, setState] = useState<"open" | "decided">("open");
  const [picked, setPicked] = useState<string | null>(null);
  const qc = useQueryClient();
  const view = useQuery({
    queryKey: ["outliers", projectId, group],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/outliers", {
          params: { path: { project_id: projectId }, query: group ? { group } : {} },
        }),
      ),
  });
  const v = view.data;
  const changed = () => void qc.invalidateQueries({ queryKey: ["outliers", projectId] });
  const band = useMutation({
    mutationFn: async (b: { low: number; high: number }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/outliers/band", {
          params: { path: { project_id: projectId } },
          body: b,
        }),
      ),
    onSuccess: changed,
  });
  const apply = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/outliers/apply", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: (_, __, ___) => {
      changed();
      void qc.invalidateQueries({ queryKey: ["patches", projectId] });
      // The earliest step the calls changed, and every step after it, asked again.
      const kinds = view.data?.pending ?? [];
      const first = (["data", "group", "invalid"] as const).find((k) => kinds.includes(k));
      const from = first ? FROM[first] : null;
      if (from) stepChanged(qc, projectId, from);
    },
  });
  if (!v) return <p className="empty">{view.error?.message ?? t.project.loading}</p>;
  if (!v.ready) return <p className="wiz-from">{o.notReady}</p>;
  const g = v.group ?? "";
  const lows = v.outliers.filter((s) => s.ratio < v.low);
  const highs = v.outliers.filter((s) => s.ratio > v.high);
  const decided = v.outliers.filter((s) => s.call);
  const shown = v.outliers
    .filter((s) => (which === "low" ? s.ratio < v.low : which === "high" ? s.ratio > v.high : true))
    .filter((s) => (state === "open" ? !s.call : !!s.call));
  const pick =
    picked && v.outliers.some((s) => s.key_sale === picked) ? picked : (shown[0]?.key_sale ?? null);
  const fmt = (x: number | null | undefined) => money(x, currency);
  return (
    <div className="ol">
      <div className="ol-bar">
        <Choice
          label={o.group}
          value={g}
          options={v.groups.map((x) => [x.id, `${x.name} (${x.outliers})`] as [string, string])}
          onChange={(x) => {
            setGroup(x);
            setPicked(null);
          }}
        />
        <BandBox low={v.low} high={v.high} set={(b) => band.mutate(b)} />
        <Seg
          label={o.group}
          value={which}
          options={[
            ["all", o.which.all({ n: v.outliers.length })],
            ["low", o.which.low({ n: lows.length })],
            ["high", o.which.high({ n: highs.length })],
          ]}
          onChange={setWhich}
        />
        <Seg
          value={state}
          options={[
            ["open", o.state.open({ n: v.outliers.length - decided.length })],
            ["decided", o.state.decided({ n: decided.length })],
          ]}
          onChange={setState}
        />
      </div>
      {v.pending.length > 0 && (
        <div className="ol-apply">
          <span>
            {o.pending({
              n: v.to_apply,
              what: v.pending.map((k) => o.pendingWhat[k as Exclude<Why, "model">]).join(", "),
            })}
          </span>
          <Button className="button primary" isDisabled={apply.isPending} onPress={() => apply.mutate()}>
            {o.apply}
          </Button>
        </div>
      )}
      {v.outliers.length === 0 ? (
        <p className="wiz-from">{o.none({ low: num(v.low, 2), high: num(v.high, 2) })}</p>
      ) : (
        <>
          <div className="ol-top">
            <OutlierMap
              points={v.points}
              picked={pick}
              low={v.low}
              high={v.high}
              pick={setPicked}
              projectId={projectId}
            />
            <div className="ol-list">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{o.cols.address}</th>
                    <th className="num">{o.cols.ratio}</th>
                    <th className="num">{o.cols.sold}</th>
                    <th className="num">{o.cols.valued}</th>
                    <th>{o.cols.date}</th>
                    <th>{o.cols.call}</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((s) => (
                    <tr
                      key={s.key_sale}
                      className={s.key_sale === pick ? "on" : undefined}
                      onClick={() => setPicked(s.key_sale)}
                    >
                      <td>
                        <Button className="ol-link" onPress={() => setPicked(s.key_sale)}>
                          {s.address ?? s.key}
                        </Button>
                      </td>
                      <td className="num">
                        <RatioPill ratio={s.ratio} low={v.low} />
                      </td>
                      <td className="num">{fmt(s.price)}</td>
                      <td className="num">{fmt(s.value)}</td>
                      <td>{s.date.slice(0, 7)}</td>
                      <td>
                        {s.call ? (
                          <span className={s.applied || s.call === "model" ? "ol-tag done" : "ol-tag"}>
                            {o.calls[s.call]}
                            {!s.applied && s.call !== "model" && ` · ${o.toApply}`}
                          </span>
                        ) : (
                          o.open
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {pick && (
            <SaleCard key={pick} projectId={projectId} keySale={pick} currency={currency} low={v.low} />
          )}
        </>
      )}
      <CommonCard projectId={projectId} group={g} />
      <PatchesCard projectId={projectId} />
    </div>
  );
}

function RatioPill({ ratio, low }: { ratio: number; low: number }) {
  return <span className={ratio < low ? "ol-pill lo" : "ol-pill hi"}>{num(ratio, 2)}</span>;
}

/** The band: typed freely, kept on leaving a box when both make sense. */
function BandBox({
  low,
  high,
  set,
}: {
  low: number;
  high: number;
  set: (b: { low: number; high: number }) => void;
}) {
  const [lo, setLo] = useState<string | null>(null);
  const [hi, setHi] = useState<string | null>(null);
  const keep = () => {
    const a = Number(lo ?? low);
    const b = Number(hi ?? high);
    if (a > 0 && a < 1 && b > 1 && b < 10 && (a !== low || b !== high)) set({ low: a, high: b });
    setLo(null);
    setHi(null);
  };
  return (
    <span className="ol-band">
      <span className="mo-label">{o.outside}</span>
      <Field
        label={o.outside}
        type="number"
        width="short"
        value={lo ?? String(low)}
        onChange={setLo}
        onBlur={keep}
      />
      <span>{o.to}</span>
      <Field
        label={o.to}
        type="number"
        width="short"
        value={hi ?? String(high)}
        onChange={setHi}
        onBlur={keep}
      />
    </span>
  );
}

function OutlierMap({
  points,
  picked,
  low,
  high,
  pick,
  projectId,
}: {
  points: S["OutlierPoint"][];
  picked: string | null;
  low: number;
  high: number;
  pick: (k: string) => void;
  projectId: string;
}) {
  const detail = useSaleDetail(projectId, picked);
  const members = detail.data?.members;
  const layers = useMemo(() => {
    const colour = (p: S["OutlierPoint"]) => (p.ratio < low ? LOW : p.ratio > high ? HIGH : WITHIN);
    const me = points.find((p) => p.key_sale === picked);
    const compPts = members ?? [];
    return [
      new ScatterplotLayer<S["OutlierPoint"]>({
        id: "sales",
        data: points,
        getPosition: (p) => [p.lon, p.lat],
        getRadius: (p) => (p.out ? 5 : 3),
        radiusUnits: "pixels",
        getFillColor: (p) => rgba(colour(p), p.out ? 0.95 : 0.55),
        pickable: true,
        onClick: ({ object }) => {
          if (object?.out) pick(object.key_sale);
        },
      }),
      new ScatterplotLayer<S["OutlierMember"]>({
        id: "comps",
        data: compPts,
        getPosition: (c) => [c.lon, c.lat],
        getRadius: 8,
        radiusUnits: "pixels",
        filled: false,
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 2,
        getLineColor: rgba("#444444"),
      }),
      ...(me
        ? [
            new ScatterplotLayer<S["OutlierPoint"]>({
              id: "picked",
              data: [me],
              getPosition: (p) => [p.lon, p.lat],
              getRadius: 9,
              radiusUnits: "pixels",
              getFillColor: (p) => rgba(colour(p)),
              stroked: true,
              lineWidthUnits: "pixels",
              getLineWidth: 3,
              getLineColor: rgba("#111111"),
            }),
          ]
        : []),
    ];
  }, [points, picked, members, low, high, pick]);
  return (
    <div className="ol-mapbox">
      <MapView
        className="ol-map"
        label={o.mapLabel}
        layers={layers}
        bounds={boundsOf(points.map((p) => [p.lon, p.lat] as const))}
        fitKey={`${points.length}:${points[0]?.key_sale ?? ""}`}
        tooltip={({ object: p }) => (p && "ratio" in p ? `${num(p.ratio, 2)}` : null)}
      />
      <div className="rv-legend">
        <span>
          <span className="rv-swatch" style={{ background: LOW }} />
          {o.legend.under({ low: num(low, 2) })}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: WITHIN }} />
          {o.legend.within({ low: num(low, 2), high: num(high, 2) })}
        </span>
        <span>
          <span className="rv-swatch" style={{ background: HIGH }} />
          {o.legend.over({ high: num(high, 2) })}
        </span>
        <span>
          <span className="rv-swatch ol-ring" />
          {o.legend.comps}
        </span>
      </div>
    </div>
  );
}

function useSaleDetail(projectId: string, keySale: string | null) {
  return useQuery({
    queryKey: ["outliers", projectId, "sale", keySale],
    enabled: !!keySale,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/outliers/sale/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: keySale ?? "" } },
        }),
      ),
  });
}

function SaleCard({
  projectId,
  keySale,
  currency,
  low,
}: {
  projectId: string;
  keySale: string;
  currency: string;
  low: number;
}) {
  const d = useSaleDetail(projectId, keySale).data;
  if (!d) return <p className="wiz-from">{o.loading}</p>;
  const s = d.sale;
  const fmt = (x: number | null | undefined) => money(x, currency);
  return (
    <div className="ol-detail">
      <div className="ol-facts">
        <h3>
          {s.address ?? s.key} <RatioPill ratio={s.ratio} low={low} />
        </h3>
        <dl className="ol-dl">
          <dt>{o.sold}</dt>
          <dd>{o.soldLine({ price: fmt(s.sold), date: day(s.date), adjusted: fmt(s.price) })}</dd>
          <dt>{o.valuedAt}</dt>
          <dd>{o.valuedLine({ value: fmt(s.value) })}</dd>
          {s.roll !== null && (
            <>
              <dt>{o.roll}</dt>
              <dd>{fmt(s.roll)}</dd>
            </>
          )}
          {d.comps_say !== null && d.basis && (
            <>
              <dt>{o.compsSay}</dt>
              <dd>
                {o.compsSayLine[d.basis]({
                  value: fmt(d.comps_say),
                  per: fmt(d.per_area),
                  ratio: num(d.comps_ratio, 2),
                })}
              </dd>
            </>
          )}
        </dl>
        {d.at_sale.length > 0 && (
          <>
            <h4>{o.atSale}</h4>
            <p className="wiz-from">{o.atSaleLede}</p>
            <dl className="ol-dl">
              {d.at_sale.map(([c = "", v = ""]) => (
                <Fragment key={c}>
                  <dt>
                    <code>{c}</code>
                  </dt>
                  <dd>{v}</dd>
                </Fragment>
              ))}
            </dl>
          </>
        )}
        <h4>{o.comps}</h4>
        {d.basis ? (
          <p className="wiz-from">
            {o.compsHow({ n: d.n_comps, depth: d.depth, full: d.full_depth })}{" "}
            {d.conditions.map((c) => `${c.name} ${c.words}`).join("; ")}
          </p>
        ) : (
          <p className="wiz-from">{o.noComps}</p>
        )}
        <table className="tbl">
          <thead>
            <tr>
              <th />
              <th className="num">{o.cols.sold}</th>
              <th className="num">{o.cols.ratio}</th>
              {d.compared.map((f) => (
                <th key={f} className="num">
                  {d.names[f] ?? f}
                </th>
              ))}
              <th className="num">{o.away}</th>
            </tr>
          </thead>
          <tbody>
            <tr className="on">
              <td>{o.thisSale}</td>
              <td className="num">{fmt(s.price)}</td>
              <td className="num">{num(s.ratio, 2)}</td>
              {d.compared.map((f) => (
                <td key={f} className="num">
                  {d.mine[f] ?? "—"}
                </td>
              ))}
              <td className="num">—</td>
            </tr>
            {d.comps.map((c) => (
              <tr key={c.key_sale}>
                <td>{c.address ?? c.key}</td>
                <td className="num">{fmt(c.price)}</td>
                <td className="num">{num(c.ratio, 2)}</td>
                {d.compared.map((f) => (
                  <td key={f} className="num">
                    {c.fields[f] ?? "—"}
                  </td>
                ))}
                <td className="num">{c.away !== null ? `${num(c.away, 2)} ${d.units}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="ol-unlike">
        <h3>{o.unlike}</h3>
        <p className="wiz-from">{o.unlikeLede}</p>
        <table className="tbl">
          <thead>
            <tr>
              <th>{o.field}</th>
              <th className="num">{o.thisParcel}</th>
              <th className="num">{o.itsComps}</th>
              <th>{o.among}</th>
              <th>{o.inModel}</th>
            </tr>
          </thead>
          <tbody>
            {d.unlike.map((u) => (
              <tr key={u.field} className={u.flag ? "ol-flag" : undefined}>
                <td>{u.name}</td>
                <td className="num">{u.this ?? o.blank}</td>
                <td className="num">{u.comps ?? "—"}</td>
                <td>
                  {u.pct !== null ? (
                    <span className="ol-bar-among" title={`${num(u.pct, 0)}`}>
                      <span className="ol-mid" />
                      <span className="ol-mark" style={{ left: `${Math.max(0, Math.min(100, u.pct))}%` }} />
                    </span>
                  ) : u.share !== null ? (
                    o.share({ pct: pct(u.share) })
                  ) : (
                    "—"
                  )}
                </td>
                <td>{u.in_model ? o.yes : o.no}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Decide projectId={projectId} detail={d} />
    </div>
  );
}

type Detail = NonNullable<ReturnType<typeof useSaleDetail>["data"]>;

function Decide({ projectId, detail }: { projectId: string; detail: Detail }) {
  const s = detail.sale;
  const [why, setWhy] = useState<Why | null>(s.call ?? null);
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState(s.note);
  const [field, setField] = useState<string | null>(null);
  const [now, setNow] = useState("");
  const [source, setSource] = useState("");
  const [to, setTo] = useState<string | null>(null);
  const qc = useQueryClient();
  // A call is on the list only until applied: only an applied call taken back changes a step.
  const after = (w: Why | null, applied: boolean) => {
    void qc.invalidateQueries({ queryKey: ["outliers", projectId] });
    void qc.invalidateQueries({ queryKey: ["patches", projectId] });
    const from = w && applied ? FROM[w] : null;
    if (from) stepChanged(qc, projectId, from);
  };
  const call = useMutation({
    mutationFn: async (body: S["OutlierCallBody"]) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/outliers/call/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: s.key_sale } },
          body,
        }),
      ),
    onSuccess: () => after(null, false),
  });
  const undo = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE("/api/projects/{project_id}/outliers/call/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: s.key_sale } },
        }),
      ),
    onSuccess: () => after(s.call ?? null, s.applied),
  });
  const pf = detail.patchable.find((p) => p.field === field);
  return (
    <div className="ol-decide">
      <h3>{o.why}</h3>
      {s.call ? (
        <p>
          <span className={s.applied || s.call === "model" ? "ol-tag done" : "ol-tag"}>
            {o.decided({ call: o.calls[s.call] })}
            {!s.applied && s.call !== "model" && ` · ${o.toApply}`}
          </span>{" "}
          {s.note}{" "}
          <Button className="button" isDisabled={undo.isPending} onPress={() => undo.mutate()}>
            {o.undo}
          </Button>
        </p>
      ) : (
        <>
          <div className="ol-whys">
            {WHYS.map((w) => (
              <Button key={w} className={w === why ? "ol-why on" : "ol-why"} onPress={() => setWhy(w)}>
                <b>{o.whys[w].title}</b>
                <span>{o.whys[w].lede}</span>
              </Button>
            ))}
          </div>
          {why === "invalid" && (
            <div className="ol-form">
              <Choice
                label={o.reason}
                value={reason}
                options={REASONS.map((r) => [r, o.reasons[r]] as [Reason, string])}
                onChange={setReason}
              />
              <Field label={o.note} value={note} onChange={setNote} width="long" />
              <div>
                <Button
                  className="button primary"
                  isDisabled={!reason || (reason === "other" && !note.trim()) || call.isPending}
                  onPress={() => call.mutate({ why, reason, note, source: "" })}
                >
                  {o.leaveOut}
                </Button>{" "}
                <span className="wiz-from">{o.leaveOutNote}</span>
              </div>
            </div>
          )}
          {why === "data" && (
            <div className="ol-form">
              <Choice
                label={o.patchField}
                value={field}
                options={detail.patchable.map((p) => [p.field, p.name] as [string, string])}
                onChange={setField}
              />
              {pf && (
                <p className="wiz-from">
                  {o.is}: {pf.now ?? o.blank}
                </p>
              )}
              <Field label={o.shouldBe} value={now} onChange={setNow} width="short" />
              <Field label={o.source} value={source} onChange={setSource} width="long" tip={o.sourceHint} />
              <div>
                <Button
                  className="button primary"
                  isDisabled={!field || !now.trim() || call.isPending}
                  onPress={() => call.mutate({ why, field, now, source, note })}
                >
                  {o.patchIt}
                </Button>{" "}
                <span className="wiz-from">{o.patchNote}</span>
              </div>
            </div>
          )}
          {why === "group" && (
            <div className="ol-form">
              <Choice
                label={o.moveTo}
                value={to}
                options={detail.groups.map(([id, name]) => [id, name] as [string, string])}
                onChange={setTo}
              />
              <Field label={o.note} value={note} onChange={setNote} width="long" />
              <div>
                <Button
                  className="button primary"
                  isDisabled={!to || call.isPending}
                  onPress={() => call.mutate({ why, group: to, note, source: "" })}
                >
                  {o.move}
                </Button>{" "}
                <span className="wiz-from">{o.moveNote}</span>
              </div>
              <p className="wiz-from">{o.orRule}</p>
            </div>
          )}
          {why === "model" && (
            <div className="ol-form">
              <p className="wiz-from">{o.modelLede}</p>
              <Field label={o.modelNote} value={note} onChange={setNote} width="long" />
              <div>
                <Button
                  className="button primary"
                  isDisabled={!note.trim() || call.isPending}
                  onPress={() => call.mutate({ why, note, source: "" })}
                >
                  {o.noteIt}
                </Button>
              </div>
            </div>
          )}
          {call.error && (
            <p className="error" role="alert">
              {call.error.message}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function CommonCard({ projectId, group }: { projectId: string; group: string }) {
  const c = useQuery({
    queryKey: ["outliers", projectId, "common", group],
    enabled: !!group,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/outliers/common/{group}", {
          params: { path: { project_id: projectId, group } },
        }),
      ),
  });
  const d = c.data;
  const off = (x: number) =>
    Math.abs(x) < 0.005 ? o.offNone : x < 0 ? o.offLow({ pct: pct(-x) }) : o.offHigh({ pct: pct(x) });
  return (
    <div className="ol-common">
      <h3>{o.common}</h3>
      <p className="wiz-from">{o.commonLede}</p>
      {!d ? (
        <p className="wiz-from">{o.loading}</p>
      ) : d.patterns.length === 0 ? (
        <p className="wiz-from">{o.noneCommon}</p>
      ) : (
        <table className="tbl">
          <thead>
            <tr>
              <th>{o.cSales}</th>
              <th className="num">{o.cSales}</th>
              <th className="num">{o.cMisses}</th>
              <th>{o.cOff}</th>
              <th>{o.cRest}</th>
              <th className="num">{o.cShare}</th>
              <th>{o.inModel}</th>
            </tr>
          </thead>
          <tbody>
            {d.patterns.map((p) => (
              <tr key={p.field}>
                <td>
                  {p.bucket}
                  {p.goes_with && <span className="wiz-from"> · {o.goesWith({ name: p.goes_with })}</span>}
                </td>
                <td className="num">{num(p.n)}</td>
                <td className="num">{num(p.misses)}</td>
                <td className={p.off < 0 ? "ol-lo" : "ol-hi"}>{off(p.off)}</td>
                <td>{off(p.rest_off)}</td>
                <td className="num">{pct(p.share)}</td>
                <td>{p.in_model ? o.yes : o.no}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {d && d.clustered !== null && (
        <p className="wiz-from">{d.clustered ? o.clustered({ i: num(d.moran, 2) }) : o.notClustered}</p>
      )}
    </div>
  );
}

function PatchesCard({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["patches", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/patches", { params: { path: { project_id: projectId } } }),
      ),
  });
  const remove = useMutation({
    mutationFn: async (i: number) =>
      unwrap(
        await api.DELETE("/api/projects/{project_id}/patches/{i}", {
          params: { path: { project_id: projectId, i } },
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["patches", projectId], data);
      void qc.invalidateQueries({ queryKey: ["outliers", projectId] });
      stepChanged(qc, projectId, "bring-in");
    },
  });
  const rows = list.data ?? [];
  return (
    <div className="ol-patches">
      <h3>{o.patches}</h3>
      <p className="wiz-from">{o.patchesLede}</p>
      {rows.length === 0 ? (
        <p className="wiz-from">{o.noPatches}</p>
      ) : (
        <>
          <table className="tbl">
            <thead>
              <tr>
                <th>{o.patchCols.parcel}</th>
                <th>{o.patchCols.field}</th>
                <th className="num">{o.patchCols.was}</th>
                <th className="num">{o.patchCols.now}</th>
                <th>{o.patchCols.source}</th>
                <th>{o.patchCols.by}</th>
                <th>{o.patchCols.at}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.i}>
                  <td>{p.key}</td>
                  <td>{p.name}</td>
                  <td className="num">{p.was ?? o.blank}</td>
                  <td className="num">{p.now}</td>
                  <td>{p.source}</td>
                  <td>{p.by}</td>
                  <td>{p.at.replace("T", " ")}</td>
                  <td>
                    <Button
                      className="button"
                      isDisabled={remove.isPending}
                      onPress={() => remove.mutate(p.i)}
                    >
                      {o.remove}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <a className="button" href={`/api/projects/${projectId}/patches/csv`} download="patches.csv">
            {o.export}
          </a>
        </>
      )}
    </div>
  );
}
