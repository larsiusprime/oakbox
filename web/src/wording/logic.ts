/** Wording that needs code before its message (SPEC §6.6): a list joined, a case changed, a number worked out or
 * rounded, a choice between messages. The words are all in en.json; this only picks the message and works out its
 * arguments. Each keeps the place and the arguments it had in `t`, so `say.wizard.left(n, what)`. */
import type { Machine } from "../api/client";
import { t } from "./catalog";

const lower = (s: string) => s.toLowerCase();
// A message's own text can start with the live editor's invisible markers (npm run dev:wording): they're kept in front.
const LEAD = "[\u200C\u200D\u2060-\u2064\uFEFF]*";
const dropLead = (s: string, word: string) => s.replace(new RegExp(`^(${LEAD})${word}`), "$1");
// "3. Sales" → "Sales": a tab's name without its number.
const unnumbered = (s: string) => dropLead(s, "\\d+\\.? ");
const list = (xs: string[]) => xs.join(", ");

type Kinds = typeof t.wizard.reconcile.kinds;
// Reconcile's labels for what's being matched (sales to parcels, a file's rows to parcels or to sales).
function reconcileLabels(k: Kinds[keyof Kinds], file = "") {
  const text = (m: string | ((a: { file: string | number }) => string)) =>
    typeof m === "string" ? m : m({ file });
  return {
    title: text(k.title),
    lede: text(k.lede),
    meter: (pct: string) => k.meter({ pct, file }),
    target: k.target,
    mine: text(k.mine),
    targetCol: text(k.targetCol),
    targetHit: k.targetHit,
    targetMiss: k.targetMiss,
    mineCol: k.mineCol,
    targetShown: (n: number, total: number) => k.targetShown({ n, total }),
    mineShown: (n: number, total: number) => k.mineShown({ n, total }),
    unmatched: (n: number, left: number) =>
      n === left ? k.unmatched.all({ left }) : k.unmatched.some({ n, left }),
  };
}

export const say = {
  inputFiles: {
    file: (filename: string, layer: string | null) => t.inputFiles.file({ filename, layer: layer || null }),
  },
  wizard: {
    left: (n: number, what: string[] = []) =>
      n <= 3 && what.length === n
        ? t.wizard.left.listed({ n, what: what.join("; ") })
        : t.wizard.left.count({ n }),
    rule: { titleFor: (name: string) => t.wizard.rule.titleFor({ name: lower(name) }) },
    numbers: {
      scales: (s: number) => {
        const m = t.wizard.numbers.scales;
        if (s === 1) return m.asWritten;
        if (s === 1000) return m.thousands;
        if (s === 1_000_000) return m.millions;
        if (s === 0.01) return m.cents;
        return s > 1 ? m.times({ by: s.toLocaleString() }) : m.divided({ by: (1 / s).toLocaleString() });
      },
      assessed: (ratio: number, field: string) =>
        t.wizard.numbers.assessed({
          ratio: ratio.toLocaleString(undefined, { maximumSignificantDigits: 3 }),
          field,
        }),
    },
    areaUnitFor: (name: string) => t.wizard.areaUnitFor({ name: lower(name) }),
    enrich: {
      summary: (labels: string[]) => (labels.length ? list(labels) : t.wizard.enrich.summary.none),
      fieldsOf: (on: number, all: number) =>
        on === all ? t.wizard.enrich.fieldsOf.all({ all }) : t.wizard.enrich.fieldsOf.some({ on, all }),
    },
    values: {
      button: (n: number, noun?: string) =>
        noun === undefined ? t.wizard.values.button.values({ n }) : t.wizard.values.button.named({ n, noun }),
    },
    units: {
      fileMostly: (n: number, rows: number) =>
        n === rows ? t.wizard.units.fileMostly.all({ rows }) : t.wizard.units.fileMostly.some({ n, rows }),
      matched: (column: string | null, v: string) => t.wizard.units.matched({ column: column || null, v }),
      summary: {
        carries: (names: string[], file: string) =>
          names.length
            ? t.wizard.units.summary.carries.some({ names: list(names), file })
            : t.wizard.units.summary.carries.none({ file }),
      },
    },
    location: {
      centerSet: (lat: number, lon: number) =>
        t.wizard.location.centerSet({ lat: lat.toFixed(5), lon: lon.toFixed(5) }),
    },
    reconcile: {
      kinds: {
        sales: () => reconcileLabels(t.wizard.reconcile.kinds.sales),
        parcels: (file: string) => reconcileLabels(t.wizard.reconcile.kinds.parcels, file),
        more_sales: (file: string) => reconcileLabels(t.wizard.reconcile.kinds.more_sales, file),
      },
      describe: {
        remove: (chars: string) => {
          const m = t.wizard.reconcile.describe.remove;
          return chars === "-" ? m.hyphens : chars === " " ? m.spaces : m.chars({ chars });
        },
      },
    },
    quality: {
      meaningOf: (name: string) => t.wizard.quality.meaningOf({ name: lower(name) }),
      byPriceLede: (type: string, field: string) =>
        type ? t.wizard.quality.byPriceLede.within({ type, field }) : t.wizard.quality.byPriceLede.all,
      rises: (basis: string) =>
        t.wizard.quality.rises({
          basis: basis.replace(new RegExp(`^(${LEAD})(.)`), (_, lead, c) => lead + c.toUpperCase()),
        }),
    },
    notLoaded: (file: string, columns: string[]) => {
      const shown = list(columns.slice(0, 4));
      return columns.length > 4
        ? t.wizard.notLoaded.more({ file, columns: shown, more: columns.length - 4 })
        : t.wizard.notLoaded.few({ file, columns: shown });
    },
  },
  tabs: {
    waits: (asked: string, shown: string) =>
      t.tabs.waits({ asked: unnumbered(asked), shown: unnumbered(shown) }),
    runAgain: (step: string) => t.tabs.runAgain({ step: unnumbered(step) }),
    pressLooksRight: (step: string) => t.tabs.pressLooksRight({ step: unnumbered(step) }),
  },
  step: {
    running: (elapsed: string, left: string | null) => t.step.running({ elapsed, left: left || null }),
  },
  bringIn: {
    detail: {
      outside: (below: number, above: number) => t.bringIn.detail.outside({ n: below + above }),
      summary: (rows: number, blank: number, distinct: number, kind: string) =>
        t.bringIn.detail.summary({ rows, blank, distinct, kind: kind === "yes/no" ? "yesno" : kind }),
    },
  },
  sales: {
    time: {
      perYear: (p: number) => t.sales.time.perYear({ sign: p >= 0 ? "+" : "−", p: Math.abs(p).toFixed(1) }),
      tip: (price: string, per: string, perWhat: string) =>
        t.sales.time.tip({ price, per, perWhat: dropLead(perWhat, "price ") }),
    },
    fill: { auto: (n: number) => t.sales.fill.auto({ n: n + 1 }) },
    review: {
      related: {
        feet: (m: number) => t.sales.review.related.feet({ n: Math.round(m * 3.28084) }),
        metres: (m: number) => t.sales.review.related.metres({ n: Math.round(m) }),
      },
      data: (area: string, unit: string, vacant: boolean, year: number | null | undefined, raw: string) =>
        t.sales.review.data({ area, unit, vacant, year: year ? String(year) : null, raw }),
    },
  },
  values: {
    lag: { split: (k: number) => t.values.lag.split({ k: k + 1 }) },
    vartest: { empty: (names: string[]) => t.values.vartest.empty({ names: list(names) }) },
    lists: {
      notTestedIn: (groups: string[]) => t.values.lists.notTestedIn({ groups: list(groups) }),
      missing: (fields: string[]) => t.values.lists.missing({ fields: list(fields) }),
    },
    small: {
      unvalued: (parcels: number, groups: string[]) =>
        t.values.small.unvalued({ parcels, n: groups.length, groups: list(groups) }),
    },
    final: { ran: (at: string, secs: number) => t.values.final.ran({ at, secs: Math.round(secs) }) },
    model: { unlisted: (groups: string[]) => t.values.model.unlisted({ groups: list(groups) }) },
  },
  /** Why the check put this computer in its tier (as machine.tier_of decides it: the first reason that holds). */
  machineWhy: (m: Machine, have: number | null | undefined) => {
    if (m.cancelled) return t.machine.whyCancelled;
    if (m.tier === "strong") return t.machine.whyStrong;
    if (m.tier === "standard") return t.machine.whyStandard;
    if (m.memory_gb < 12) return t.machine.whyMemory({ gb: Math.round(m.memory_gb), have: have ?? 0 });
    if (m.cores <= 2) return t.machine.whyCores;
    return t.machine.whySpeed;
  },
  /** One line of what the check found, for Settings. */
  machineSpecs: (m: Machine) =>
    t.settings.specs({
      gb: Math.round(m.memory_gb),
      processor: m.processor || t.machine.processorValue({ cores: m.cores }),
      speed: m.speed ?? t.settings.noValue,
      disk: m.disk_mb_s != null ? t.machine.diskValue({ mbs: m.disk_mb_s }) : t.settings.noValue,
      graphics: m.graphics ?? t.machine.graphicsNone,
    }),
};
