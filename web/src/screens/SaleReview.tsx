/** Check sales' review of the sales set aside: the list, one sale at a time, and why each was set aside. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Button, TextArea, TextField } from "react-aria-components";
import {
  api,
  type CleanView,
  type RelatedSale,
  type ReviewItem,
  type SaleDetail,
  unwrap,
} from "../api/client";
import { stepChanged, stepKey } from "../api/steps";
import { Choice } from "../components/Form";
import { desktop } from "../desktop";
import { day, money, num } from "../lib/format";
import { useWidth } from "../lib/hooks";
import { t } from "../strings";

const s = t.sales;
type Unit = "sqft" | "sqm";

/** A price against its group's median: "16.4× the median", "0.37× the median", "1/55,000 of the median". */
function rel(r: number, of: string): string {
  if (r >= 0.1) return `${num(r, r >= 10 ? 0 : r >= 1 ? 1 : 2)}× ${of}`;
  return `1/${num(Math.round(1 / r))} of ${of}`;
}

// ---------- The review: the sales set aside ----------

export function useReviewCounts(projectId: string) {
  return useQuery({
    queryKey: ["clean-review", projectId, "", "", ""],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review", {
          params: { path: { project_id: projectId }, query: { limit: 1 } },
        }),
      ),
  }).data;
}

type Status = "" | "undecided" | "kept" | "excluded";

export function Review({
  projectId,
  currency,
  place,
  check,
  setCheck,
  view,
  rerun,
}: {
  projectId: string;
  currency: string;
  place: string;
  check: string;
  setCheck: (c: string) => void;
  view: CleanView;
  rerun: () => void;
}) {
  const [group, setGroup] = useState("");
  const [status, setStatus] = useState<Status>("");
  const [picked, setPicked] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["clean-review", projectId, group, check, status],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review", {
          params: {
            path: { project_id: projectId },
            query: {
              group,
              status,
              limit: 500,
              ...(check.startsWith("pattern:") ? { pattern: check.slice(8) } : { check }),
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const page = list.data;
  const items = page?.items ?? [];
  const current = items.find((i) => i.key_sale === picked) ?? items[0] ?? null;
  const next = () => {
    const i = items.findIndex((x) => x.key_sale === current?.key_sale);
    const n = items[i + 1];
    if (n) setPicked(n.key_sale);
  };
  // Another sale set aside (one on the same deed, say): open it, widening the filters if they hide it.
  const pick = (key: string) => {
    if (!items.some((x) => x.key_sale === key)) {
      setGroup("");
      setStatus("");
      setCheck("");
    }
    setPicked(key);
  };
  const checks: [string, string][] = [
    ["", s.review.everyCheck],
    ...Object.entries(s.review.checkNames),
    ...Object.entries(s.review.diagnosis).map(([k, v]) => [`pattern:${k}`, v.name] as [string, string]),
  ];
  return (
    <div className="cs-review">
      <div className="cs-filters">
        <b>{s.review.title(page?.all ?? 0)}</b>
        <Choice
          label={s.group}
          hideLabel
          value={group}
          options={[
            ["", s.review.allGroups],
            ...(page?.groups ?? []).map((g) => [g.value, g.label] as [string, string]),
          ]}
          onChange={setGroup}
        />
        <Choice label={s.review.check} hideLabel value={check} options={checks} onChange={setCheck} />
        <Choice
          label={s.review.status}
          hideLabel
          value={status}
          options={[
            ["", s.review.anyStatus],
            ["undecided", s.review.undecided(page?.undecided ?? 0)],
            ["kept", s.review.kept(page?.kept ?? 0)],
            ["excluded", s.review.excluded(page?.excluded ?? 0)],
          ]}
          onChange={(v) => setStatus(v as Status)}
        />
        <span className="bi-grow" />
        {view.stale ? (
          <span className="wiz-warn">
            {s.review.apply}{" "}
            <Button className="button" onPress={rerun}>
              {s.runAgain}
            </Button>
          </span>
        ) : (
          <span className="wiz-from">{s.review.applyLater}</span>
        )}
      </div>
      {items.length === 0 ? (
        <p className="wiz-from">{s.review.empty}</p>
      ) : (
        <div className="cs-split">
          <ul className="cs-list" aria-label={s.review.listLabel}>
            {items.map((i) => (
              <li key={i.key_sale}>
                <button
                  type="button"
                  className={i.key_sale === current?.key_sale ? "cs-item sel" : "cs-item"}
                  onClick={() => setPicked(i.key_sale)}
                >
                  <b>{i.address ?? i.key}</b>
                  <span>
                    {money(i.price, currency)}
                    {i.price_per_area !== null && i.price_per_area !== undefined && (
                      <>
                        {" · "}
                        {money(i.price_per_area, currency)}/{s.unit[(page?.unit ?? "sqft") as Unit]}
                        {i.ratio ? ` · ${rel(i.ratio, s.review.itsGroupShort)}` : ""}
                      </>
                    )}
                  </span>
                  <span>
                    {pills(i)}
                    <span className="wiz-from"> {day(i.sale_date)}</span>
                  </span>
                </button>
              </li>
            ))}
            {page && page.total > items.length && (
              <li className="wiz-from cs-more">{s.review.more(page.total - items.length)}</li>
            )}
          </ul>
          {current && (
            <SaleView
              key={current.key_sale}
              projectId={projectId}
              item={current}
              unit={(page?.unit ?? "sqft") as Unit}
              currency={currency}
              place={place}
              next={next}
              pick={pick}
            />
          )}
        </div>
      )}
    </div>
  );
}

function pills(i: ReviewItem) {
  const out: React.ReactNode[] = [];
  if (i.status !== "undecided") {
    out.push(
      <span key="status" className={`pill ${i.status === "kept" ? "pill-ok" : ""}`}>
        {i.status === "kept" ? s.review.keptPill : s.review.excludedPill}
      </span>,
    );
  }
  if (i.ratio) {
    out.push(
      <span key="r" className={i.ratio >= 1 ? "pill pill-bad" : "pill pill-info"}>
        {i.ratio >= 1 ? s.review.high : s.review.low}
      </span>,
    );
  }
  if (i.flag_only)
    out.push(
      <span key="only" className="pill">
        {s.review.flagOnly}
      </span>,
    );
  else if (i.pattern?.split(",").includes("1"))
    out.push(
      <span key="size" className="pill">
        {s.review.oddSize}
      </span>,
    );
  for (const c of i.checks.filter((c) => c !== "cluster")) {
    out.push(
      <span key={c} className="pill">
        {s.review.checkNames[c as keyof typeof s.review.checkNames] ?? c}
      </span>,
    );
  }
  if (i.second_look)
    out.push(
      <span key="2" className="pill">
        {s.review.secondPill}
      </span>,
    );
  return out;
}

/** Why it was set aside, in plain words, from its pattern (the five anomalies) and checks. */
function why(i: ReviewItem, d: SaleDetail | undefined, currency: string, unit: Unit): string[] {
  const out: string[] = [];
  const u = s.unit[unit];
  if (i.ratio && i.median && i.price_per_area !== null && i.price_per_area !== undefined) {
    const area = d?.area ? ` ${s.review.with(num(d.area), u, i.vacant)}` : "";
    out.push(
      s.review.sold(money(i.price, currency), area, money(i.price_per_area, currency), u) +
        s.review.vs(rel(i.ratio, s.review.theMedian), (i.count ?? 1) - 1, money(i.median, currency)),
    );
  } else if (i.price !== null && i.price !== undefined) {
    out.push(s.review.soldFor(money(i.price, currency)));
  }
  for (const c of i.checks) {
    const raw = i.details[c];
    // A nominal price comes as a number: said as money.
    const found = c === "nominal_price" && raw ? money(Number(raw.replace(/,/g, "")), currency) : raw;
    const said = found && s.review.details[c];
    const text = said ? said(found) : s.review.checkWhy[c];
    if (text) out.push(text);
  }
  if (i.seller && i.buyer) out.push(s.review.sellerBuyer(i.seller, i.buyer));
  if (i.second_look) out.push(s.review.second);
  return out;
}

function SaleView({
  projectId,
  item: i,
  unit,
  currency,
  place,
  next,
  pick,
}: {
  projectId: string;
  item: ReviewItem;
  unit: Unit;
  currency: string;
  place: string;
  next: () => void;
  pick: (key: string) => void;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState(i.note);
  // A new sale opens at its top: scrolled down to Next, the page would otherwise show its middle.
  const top = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = top.current;
    if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start" });
  }, []);
  const detail = useQuery({
    queryKey: ["clean-sale", projectId, i.key_sale],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: i.key_sale } },
        }),
      ),
  });
  const mark = useMutation({
    mutationFn: async (m: { key: string; action: "keep" | "exclude" | null; note: string }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/clean/marks/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: m.key } },
          body: { action: m.action, note: m.note },
        }),
      ),
    // A mark puts Check sales out of date, and so the steps after it.
    onSuccess: (data) => {
      queryClient.setQueryData(stepKey("clean", projectId), data);
      stepChanged(queryClient, projectId, "clean", false);
    },
  });
  const d = detail.data;
  const u = s.unit[unit];
  const decide = (action: "keep" | "exclude" | null) =>
    mark.mutate({ key: i.key_sale, action, note }, { onSuccess: () => action && next() });
  return (
    <section ref={top} className="bi-card cs-detail" aria-label={i.address ?? i.key}>
      <h3>
        {i.address ?? i.key}{" "}
        <span className="wiz-from">{s.review.head(i.group_name, day(i.sale_date), i.key_sale)}</span>
      </h3>
      {why(i, d, currency, unit).map((line) => (
        <p key={line} className="cs-why">
          {line}
        </p>
      ))}
      {d && d.together.length > 1 && <Together d={d} unit={unit} currency={currency} pick={pick} />}
      <Readings i={i} unit={unit} currency={currency} />
      <Diagnosis i={i} />
      {d && <Look address={i.address} place={place} latitude={d.latitude} longitude={d.longitude} />}
      {d && d.members.length > 1 && (
        <>
          <Dots members={d.members} self={i.key_sale} median={i.median} currency={currency} />
          <p className="wiz-from cs-text">{s.review.dotsNote(u)}</p>
          <table className="tbl">
            <thead>
              <tr>
                <th>{s.review.itsGroup}</th>
                <th className="cs-n">{s.review.perArea(u)}</th>
                <th className="cs-n">{i.vacant ? s.review.land(u) : s.review.finished(u)}</th>
                <th>{s.review.soldOn}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.members.map((m) => (
                <tr key={m.key_sale} className={m.key_sale === i.key_sale ? "cs-self" : ""}>
                  <td>{m.address ?? m.key_sale}</td>
                  <td className="cs-n">{money(m.price_per_area, currency)}</td>
                  <td className="cs-n">{num(m.area)}</td>
                  <td>{day(m.sale_date)}</td>
                  <td>
                    {m.key_sale === i.key_sale ? (
                      <span className="pill pill-bad">{s.review.thisSale}</span>
                    ) : m.flagged ? (
                      <span className="pill">{s.review.setAside}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {d && (
        <Related
          related={d.related.filter((x) => !d.together.some((y) => y.key_sale === x.key_sale))}
          currency={currency}
          unit={unit}
        />
      )}
      {d && (
        <p className="wiz-from cs-text">
          {s.review.data(num(d.area), u, i.vacant, d.year_built, money(d.raw_price, currency))}
        </p>
      )}
      {/* Pinned to the bottom of the window: Keep, Exclude and Next stay put from sale to sale. */}
      <div className="cs-decide">
        <TextField className="cs-note-field" value={note} onChange={setNote} aria-label={s.review.noteLabel}>
          <TextArea className="cs-note" placeholder={s.review.notePlaceholder} />
        </TextField>
        <p className={i.status === "kept" ? "wiz-ok cs-now" : "cs-now"}>
          {i.status === "undecided"
            ? s.review.nowUndecided
            : i.status === "kept"
              ? s.review.nowKept
              : s.review.nowExcluded}
        </p>
        <div className="cs-actions">
          {i.status === "undecided" ? (
            <>
              <Button
                className="button"
                isDisabled={!i.checks.length || !note.trim() || mark.isPending}
                onPress={() => decide("keep")}
              >
                {s.review.keep}
              </Button>
              <Button className="button" isDisabled={mark.isPending} onPress={() => decide("exclude")}>
                {s.review.exclude}
              </Button>
              <span className="wiz-from">{s.review.keepNote}</span>
            </>
          ) : (
            <Button className="button" isDisabled={mark.isPending} onPress={() => decide(null)}>
              {s.review.undo}
            </Button>
          )}
          <span className="bi-grow" />
          <Button className="wiz-link" onPress={next}>
            {s.review.next}
          </Button>
        </div>
        {mark.error && (
          <p className="error" role="alert">
            {mark.error.message}
          </p>
        )}
      </div>
    </section>
  );
}

/** The sales recorded with this one (its deed, the same day; or the same day at the same price): likely one sale of
 * several parcels, each given the whole price or a share. */
function Together({
  d,
  unit,
  currency,
  pick,
}: {
  d: SaleDetail;
  unit: Unit;
  currency: string;
  pick: (key: string) => void;
}) {
  const tg = s.review.together;
  const u = s.unit[unit];
  const rows = d.together;
  const prices = rows.map((x) => x.price ?? 0);
  const same = prices.every((x) => x === prices[0]);
  const total = prices.reduce((a, b) => a + b, 0);
  return (
    <section className="cs-step">
      <h4 className="wiz-group">
        {d.together_by === "deed" && d.deed
          ? tg.onDeed(d.deed, day(d.item.sale_date), rows.length)
          : tg.samePrice(day(d.item.sale_date), rows.length)}
      </h4>
      <table className="tbl">
        <thead>
          <tr>
            <th>{tg.sale}</th>
            <th>{s.group}</th>
            <th className="cs-n">{tg.price}</th>
            <th className="cs-n">{s.review.finished(u)}</th>
            <th className="cs-n">{s.review.land(u)}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((x) => (
            <tr key={x.key_sale} className={x.this ? "cs-self" : undefined}>
              <td>{x.address ?? x.key_sale}</td>
              <td>{x.group_name}</td>
              <td className="cs-n">{money(x.price, currency)}</td>
              <td className="cs-n">{num(x.finished)}</td>
              <td className="cs-n">{num(x.land)}</td>
              <td>
                {x.this ? (
                  <span className="pill pill-bad">{s.review.thisSale}</span>
                ) : x.set_aside ? (
                  <Button className="wiz-link" onPress={() => pick(x.key_sale)}>
                    {tg.open}
                  </Button>
                ) : (
                  <span className="wiz-from">{tg.kept}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="wiz-from">
        {same
          ? tg.each(money(prices[0], currency), rows.length)
          : tg.sum(money(total, currency), rows.length)}
      </p>
    </section>
  );
}

/** Price, price per area and size against its group, as the five-pattern table reads them. */
function Readings({ i, unit, currency }: { i: ReviewItem; unit: Unit; currency: string }) {
  if (!i.per_area_rating) return null;
  const r = s.review.readings;
  const u = s.unit[unit];
  const rows: [string, string, string, number | null | undefined, string | null | undefined][] = [
    [r.price, money(i.price, currency), money(i.price_median, currency), i.price_dist, i.price_rating],
    [
      r.perArea(u),
      money(i.price_per_area, currency),
      money(i.median, currency),
      i.per_area_dist,
      i.per_area_rating,
    ],
    [r.size(u, i.vacant), num(i.size), num(i.size_median), i.size_dist, i.size_rating],
  ];
  return (
    <>
      <table className="tbl cs-readings">
        <thead>
          <tr>
            <th>{r.title}</th>
            <th className="cs-n">{r.thisSale}</th>
            <th className="cs-n">{r.median}</th>
            <th className="cs-n">{r.sd}</th>
            <th>{r.reading}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, mine, median, dist, rating]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className="cs-n">{mine}</td>
              <td className="cs-n">{median}</td>
              <td className="cs-n">{dist === null || dist === undefined ? "" : dist.toFixed(2)}</td>
              <td>
                <span
                  className={
                    rating === "in" ? "pill" : rating === "high" ? "pill pill-bad" : "pill pill-info"
                  }
                >
                  {r[(rating ?? "in") as "low" | "in" | "high"]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="wiz-from cs-text">{r.note}</p>
    </>
  );
}

/** Its pattern: the likely causes, and what to check (the five-pattern table). */
function Diagnosis({ i }: { i: ReviewItem }) {
  const key = i.flag_only ? "other" : (i.pattern ?? "").split(",").find((p) => p in s.review.diagnosis);
  const d = key ? s.review.diagnosis[key] : undefined;
  if (!d) return null;
  return (
    <div className={i.flag_only ? "cs-diag bi-warn" : "cs-diag"}>
      <b>{d.name}</b>
      <p className="cs-text">{d.why}</p>
      <b className="cs-small">{s.review.checkFor}</b>
      <ul className="cs-todo">
        {d.actions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </div>
  );
}

/** Street View, the aerial, Zillow and Redfin, in a viewer window beside the app (a browser tab outside it). */
function Look({
  address,
  place,
  latitude,
  longitude,
}: {
  address: string | null | undefined;
  place: string;
  latitude: number | null | undefined;
  longitude: number | null | undefined;
}) {
  const l = s.review.look;
  const where = address ? `${address}, ${place}` : "";
  const at = latitude != null && longitude != null ? `${latitude},${longitude}` : "";
  const links: [string, string][] = [];
  if (at) {
    links.push([l.streetView, `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${at}`]);
    links.push([
      l.aerial,
      `https://www.google.com/maps/@?api=1&map_action=map&center=${at}&zoom=19&basemap=satellite`,
    ]);
  }
  if (where) {
    links.push([l.zillow, `https://www.zillow.com/homes/${encodeURIComponent(where)}_rb/`]);
    // Redfin has no address link: the search's first Redfin result.
    links.push([
      l.redfin,
      `https://duckduckgo.com/?q=${encodeURIComponent(`!ducky site:redfin.com ${where}`)}`,
    ]);
  }
  if (!links.length) return null;
  return (
    <div className="cs-row cs-look">
      <b className="cs-small">{l.title}</b>
      {links.map(([label, url]) => (
        <Button
          key={label}
          className="button"
          onPress={() => desktop.view(url, `${label}: ${address ?? at}`)}
        >
          {label}
        </Button>
      ))}
      <span className="wiz-from">{l.note}</span>
    </div>
  );
}

/** Sales that may be the same transaction, or the same buyer's. */
function Related({ related, currency, unit }: { related: RelatedSale[]; currency: string; unit: Unit }) {
  const r = s.review.related;
  return (
    <section className="cs-step">
      <h4 className="wiz-group">{r.title}</h4>
      {related.length === 0 ? (
        <p className="wiz-from">{r.none}</p>
      ) : (
        <table className="tbl">
          <thead>
            <tr>
              <th>{r.address}</th>
              <th>{r.sold}</th>
              <th className="cs-n">{r.price}</th>
              <th className="cs-n">{r.away}</th>
              <th>{r.buyer}</th>
              <th>{r.how}</th>
            </tr>
          </thead>
          <tbody>
            {related.map((x) => (
              <tr key={x.key_sale}>
                <td>
                  {x.address ?? x.key_sale}
                  {x.set_aside && <span className="pill"> {s.review.setAside}</span>}
                </td>
                <td>{day(x.sale_date)}</td>
                <td className="cs-n">{money(x.price, currency)}</td>
                <td className="cs-n">
                  {x.distance == null ? "" : unit === "sqft" ? r.feet(x.distance) : r.metres(x.distance)}
                </td>
                <td>{x.buyer ?? ""}</td>
                <td>{x.why.map((w) => r.why[w] ?? w).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

/** The prices per area of the sales it was compared with, on a log scale: this sale red, others set aside orange. */
function Dots({
  members,
  self,
  median,
  currency,
}: {
  members: SaleDetail["members"];
  self: string;
  median: number | null | undefined;
  currency: string;
}) {
  // Drawn at its own width in pixels: all the width there is, the text staying its size.
  const [ref, w] = useWidth<SVGSVGElement>(600, 300);
  const xs = members.map((m) => m.price_per_area).filter((x): x is number => !!x && x > 0);
  if (xs.length < 2) return null;
  const lo = Math.floor(Math.log10(Math.min(...xs)));
  const hi = Math.ceil(Math.log10(Math.max(...xs)));
  const span = Math.max(1, hi - lo);
  const x = (v: number) => 40 + ((w - 80) * (Math.log10(v) - lo)) / span;
  const ticks = Array.from({ length: span + 1 }, (_, k) => 10 ** (lo + k));
  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${w} 92`}
      height="92"
      className="cs-dots"
      role="img"
      aria-label={s.review.dotsLabel}
    >
      <line x1="40" x2={w - 40} y1="62" y2="62" stroke="#888" />
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1="58" y2="66" stroke="#888" />
          <text x={x(v)} y="84" textAnchor="middle" fontSize="12" fill="#555">
            {money(v, currency)}
          </text>
        </g>
      ))}
      {median && median > 0 && (
        <g>
          <line x1={x(median)} x2={x(median)} y1="18" y2="58" stroke="#333" strokeDasharray="3 3" />
          <text x={x(median)} y="13" textAnchor="middle" fontSize="12" fill="#333">
            {s.review.median(money(median, currency))}
          </text>
        </g>
      )}
      {members
        .filter((m) => m.price_per_area && m.price_per_area > 0)
        .map((m) => (
          <circle
            key={m.key_sale}
            cx={x(m.price_per_area ?? 1)}
            cy="40"
            r={m.key_sale === self ? 7 : 5}
            fill={m.key_sale === self ? "#d33" : m.flagged ? "#e8955a" : "#6f9be0"}
            opacity="0.85"
          >
            <title>{`${m.address ?? m.key_sale}: ${money(m.price_per_area, currency)}`}</title>
          </circle>
        ))}
    </svg>
  );
}
