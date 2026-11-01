/** Check my values' scorecard and groups table: each model group against the targets, a verdict cell per question. */
import type { FieldResult, RatioStudy } from "../api/client";
import { Pill, type Verdict, verdictOf } from "../components/Pill";
import { InfoTip } from "../components/Tip";
import { num, ratioText, signed } from "../lib/format";
import { t } from "../strings";

const r = t.ratio;

/** The PRB's verdict: met within the good range, missed outside the unacceptable, near in between. */
function prbVerdict(g: RatioStudy): Verdict | null {
  const ok = g.verdict?.prb;
  if (ok != null) return verdictOf(ok);
  return g.verdict?.judged && g.prb != null ? "slight" : null;
}

/** The VEI's badge: met unless significantly outside (the exposure draft's Appendix E). */
function veiOk(g: { vei_verdict?: string | null; verdict?: { judged: boolean } | null }): boolean | null {
  if (g.vei_verdict === "compliant" || g.vei_verdict === "not_significant") return true;
  if (g.vei_verdict === "regressive" || g.vei_verdict === "progressive")
    return g.verdict?.judged ? false : null;
  return null;
}

export function judged(g: RatioStudy) {
  return !!g.verdict?.judged;
}

/** One line per model group, its three questions in columns: a mark, the figure, a word, aligned down the table so
 * groups compare at a glance. */
export function Scorecard({ groups, technical = false }: { groups: RatioStudy[]; technical?: boolean }) {
  const c = r.card;
  // Model values names the statistics, and adds horizontal equity: similar parcels, sold or not, valued alike.
  const cols = technical ? 4 : 3;
  const horizontal = (g: RatioStudy) =>
    technical && (
      <td>
        <Score
          v={null}
          figure={g.median_chd == null ? "—" : num(g.median_chd, 1)}
          word={
            g.median_chd == null
              ? c.noChd
              : g.median_chd < 20
                ? c.chdTight
                : g.median_chd < 40
                  ? c.chdSome
                  : c.chdWide
          }
          note="CHD"
        />
      </td>
    );
  return (
    <table className={technical ? "tbl rv-score rv-score-4" : "tbl rv-score"}>
      <thead>
        <tr>
          <th>{r.table.group}</th>
          <th className="cs-n">{r.table.sales}</th>
          <th>
            <InfoTip label={technical ? c.median : c.level} text={c.levelWhy} />
          </th>
          <th>
            <InfoTip label={technical ? c.cod : c.uniform} text={c.uniformWhy} />
          </th>
          {technical && (
            <th>
              <InfoTip label={c.horizontal} text={c.horizontalWhy} />
            </th>
          )}
          <th>
            <InfoTip label={technical ? c.verticalEquity : c.vertical} text={c.verticalWhy} />
          </th>
        </tr>
      </thead>
      <tbody>
        {groups.map((g) => {
          const v = g.verdict;
          const name = (
            <td>
              <span className="mg-sw ab-sw" style={{ background: g.color }} />
              {g.name}
            </td>
          );
          if (!g.sales || g.median == null)
            return (
              <tr key={g.id}>
                {name}
                <td className="cs-n">0</td>
                <td colSpan={cols} className="wiz-from">
                  {c.noSales}
                </td>
              </tr>
            );
          if (!v?.judged)
            return (
              <tr key={g.id}>
                {name}
                <td className="cs-n">{num(g.sales)}</td>
                <td>
                  <Score v={null} figure={ratioText(g.median)} />
                </td>
                <td colSpan={cols - 1} className="wiz-from">
                  {c.tooFew}
                </td>
              </tr>
            );
          // The VEI decides; with too few sales for it, the PRB.
          const byVei = g.vei_verdict && g.vei_verdict !== "insufficient";
          const tilted = byVei
            ? g.vei_verdict === "regressive" || g.vei_verdict === "progressive"
            : v.prb === false;
          const lower = byVei ? g.vei_verdict === "regressive" : (g.prb ?? 0) < 0;
          return (
            <tr key={g.id}>
              {name}
              <td className="cs-n">{num(g.sales)}</td>
              <td>
                <Score
                  v={verdictOf(v.level)}
                  figure={ratioText(g.median)}
                  word={v.level ? c.inRange : g.median < 1 ? c.low : c.high}
                />
              </td>
              <td>
                <Score
                  v={verdictOf(v.cod_low ? false : v.cod)}
                  figure={num(g.cod, 1)}
                  word={v.cod_low ? c.tooEven : v.cod === false ? c.varied : c.even}
                />
              </td>
              {horizontal(g)}
              <td>
                <Score
                  v={byVei ? verdictOf(veiOk(g)) : prbVerdict(g)}
                  figure={
                    byVei && g.vei != null
                      ? `${signed(g.vei, 1)}%`
                      : `${g.prb == null ? "—" : signed(g.prb, 3)}`
                  }
                  word={
                    tilted
                      ? lower
                        ? c.dearerLower
                        : c.dearerHigher
                      : g.vei_verdict === "not_significant"
                        ? c.notSignificant
                        : c.alike
                  }
                  note={byVei ? "VEI" : "PRB"}
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** A verdict cell: pill, figure and word in the same three columns on every row. */
export function Score({
  v,
  figure,
  word,
  note,
}: {
  v: Verdict | null;
  figure: string;
  word?: string;
  note?: string;
}) {
  return (
    <span className="rv-score-cell">
      <span className="rv-score-pill">
        <Pill v={v} />
      </span>
      <span className="rv-fig">
        {figure}
        {note && <span className="wiz-from"> {note}</span>}
      </span>
      <span>{word ?? r.card.notJudged}</span>
    </span>
  );
}

/** A figure with its pill: the pill at the cell's left edge, the figure at its right, so a pill never moves the
 * figure; every sale's figure under it. */
function cell(
  v: Verdict | null | undefined,
  text: string,
  every?: string | null,
  low?: boolean | null,
  label?: string,
) {
  return (
    <>
      <span className="rv-cell">
        <span className="rv-cell-pill">
          <Pill v={v} {...(label ? { label } : {})} />
          {low && <span className="pill pill-bad">{r.table.low}</span>}
        </span>
        <span>{text}</span>
      </span>
      {every != null && <span className="rv-every">{r.table.every(every)}</span>}
    </>
  );
}

export function GroupsTable({ result }: { result: FieldResult }) {
  const tb = r.table;
  const row = (g: RatioStudy, total = false) => {
    const v = g.verdict;
    const e = g.every;
    if (!g.sales && !g.trimmed)
      return (
        <tr key={g.id || "all"}>
          <td>
            <span className="mg-sw ab-sw" style={{ background: g.color }} />
            {g.name}
          </td>
          <td className="cs-n">0</td>
          <td colSpan={8} className="wiz-from">
            {tb.noSales}
          </td>
        </tr>
      );
    const pm = (x: number | null | undefined, d: number) => (x == null ? "—" : signed(x, d));
    return (
      <tr key={g.id || "all"} className={total ? "rv-total" : undefined}>
        <td>
          {!total && <span className="mg-sw ab-sw" style={{ background: g.color }} />}
          {g.name}
        </td>
        <td className="cs-n">{cell(null, num(g.sales), e ? num(e.sales) : null)}</td>
        <td className="cs-n">{num(g.trimmed)}</td>
        <td className="cs-n">
          {cell(verdictOf(v?.level), ratioText(g.median), e ? ratioText(e.median) : null)}
        </td>
        <td className="cs-n wiz-from">
          {g.low != null && g.high != null ? `${ratioText(g.low)} to ${ratioText(g.high)}` : "—"}
        </td>
        <td className="cs-n">
          {cell(verdictOf(v?.cod), num(g.cod, 1), e ? num(e.cod, 1) : null, v?.cod_low)}
        </td>
        <td className="cs-n">
          {g.vei_verdict
            ? cell(
                verdictOf(veiOk(g)),
                g.vei != null ? `${signed(g.vei, 1)}%` : "—",
                e?.vei != null ? `${signed(e.vei, 1)}%` : null,
                null,
                tb.verdicts[g.vei_verdict] ?? g.vei_verdict,
              )
            : "—"}
        </td>
        <td className="cs-n">{cell(prbVerdict(g), pm(g.prb, 3), e ? pm(e.prb, 3) : null)}</td>
        <td className="cs-n">{cell(null, num(g.prd, 3), e ? num(e.prd, 3) : null)}</td>
        <td className="cs-n">{cell(null, num(g.mki, 3), e ? num(e.mki, 3) : null)}</td>
      </tr>
    );
  };
  return (
    <>
      <table className="tbl">
        <thead>
          <tr>
            <th>{tb.group}</th>
            <th className="cs-n">{tb.sales}</th>
            <th className="cs-n">
              <InfoTip label={tb.trimmed} text={tb.trimmedWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.median} text={tb.medianWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.range} text={tb.rangeWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.cod} text={tb.codWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.vei} text={tb.veiWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.prb} text={tb.prbWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.prd} text={tb.prdWhy} />
            </th>
            <th className="cs-n">
              <InfoTip label={tb.mki} text={tb.mkiWhy} />
            </th>
          </tr>
        </thead>
        <tbody>{result.groups.map((g) => row(g))}</tbody>
        <tfoot>{row(result.overall, true)}</tfoot>
      </table>
      <p className="wiz-from">{tb.note}</p>
    </>
  );
}
