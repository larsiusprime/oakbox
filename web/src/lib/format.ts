/** How OAK box writes numbers, money, dates and sizes on screen: one way each, everywhere. */

/** A number, its decimals fixed; "—" for none. */
export function num(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined
    ? "—"
    : v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** A number with its sign: "+0.152", "−12.6" (a true minus). */
/** A ratio, to three places. */
export const ratioText = (v: number | null | undefined) => num(v, 3);

export function signed(v: number, digits: number): string {
  return `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
}

/** A share as a percentage, whole unless it's within one point of 0 or 100: "0.4%", "37%", "99.6%". */
export function pct(share: number): string {
  const p = 100 * share;
  return (p > 0 && p < 1) || (p > 99 && p < 100) ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

/** An amount in a currency (its ISO code): cents under 100, two significant figures under 1. */
export function money(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return "—";
  if (v !== 0 && Math.abs(v) < 1) {
    // A cent a square foot: two significant figures, not "$0.00".
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumSignificantDigits: 2,
    }).format(v);
  }
  const digits = Math.abs(v) < 100 ? 2 : 0;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v);
}

/** "$246K", "$1.3M": an amount in a currency (its ISO code), short. */
export function moneyShort(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: Math.abs(v) >= 1e6 ? 2 : 0,
  }).format(v);
}

/** "$246K", "$1.25M", "$10": an amount, short, after a currency's symbol (as the server gives it). */
export function amount(symbol: string, v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${symbol}${(v / 1e6).toLocaleString(undefined, { maximumFractionDigits: 2 })}M`;
  if (a >= 10_000) return `${symbol}${Math.round(v / 1000).toLocaleString()}K`;
  return `${symbol}${v.toLocaleString(undefined, { maximumFractionDigits: a >= 10 ? 0 : 2 })}`;
}

/** A date as the day it is: "2025-11-01"; "—" for none. */
export function day(text: string | null | undefined): string {
  return text ? text.slice(0, 10) : "—";
}

/** When something happened: "today at 14:05", or its date and time. */
export function when(iso: string): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return new Date().toDateString() === d.toDateString()
    ? `today at ${time}`
    : `${d.toLocaleDateString()} at ${time}`;
}

/** A duration on a clock: "3:07". */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** A file's size: "640 KB", "12 MB", "1.4 GB". */
export function size(bytes: number): string {
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** A row's shading: the rows of one repeated ID share it and IDs alternate (`bands`); otherwise every other row. */
export function band(bands: number[] | null | undefined, i: number): string {
  if (!bands) return i % 2 ? "band-b" : "band-a";
  return bands[i] ? "band-b" : "band-a";
}

/** A value from a file, cut to `max` characters with an ellipsis: values can be hundreds of characters with no
 * space (a county export's "#####…"), and one of them shouldn't stretch a table, a list or a dialog. Show the
 * whole value in a title where it matters. */
export function short(v: string, max = 40): string {
  return v.length > max ? `${v.slice(0, max - 1)}…` : v;
}
