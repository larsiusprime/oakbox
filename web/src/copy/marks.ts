/** Live copy editing's markers (SPEC §6.6; `npm run dev:copy` only, `__COPY_EDIT__`): each message the app shows
 * carries invisible characters naming which message it is, and with which arguments, so Alt+click finds it.
 *   START, its number in base 4 (four zero-width characters), SEP, the text, END
 * Messages nest (one message's argument can be another's text); the innermost is the one clicked. Every other build
 * has none of this: the bundle is checked for it (scripts/no-copy-edit.mjs). */

const ch = String.fromCharCode;
const START = ch(0x2063); // invisible separator
const SEP = ch(0x2064); // invisible plus
const END = ch(0x2062); // invisible times
// Zero-width, and none of them a line-break opportunity.
const DIGITS = [ch(0x200c), ch(0x200d), ch(0x2060), ch(0xfeff)];

export const SENTINEL = "oakbox-copy-edit";

/** What each marker number stands for: a message and the arguments it was shown with. */
export const shown: { key: string; args: Record<string, unknown> | null }[] = [];
const numbers = new Map<string, number>();

function encode(n: number) {
  let s = "";
  do {
    s = (DIGITS[n % 4] ?? "") + s;
    n = Math.floor(n / 4);
  } while (n > 0);
  return s;
}

export function mark(key: string, args: Record<string, unknown> | null, text: string) {
  const sig = args ? `${key}\u0000${JSON.stringify(args)}` : key;
  let n = numbers.get(sig);
  if (n === undefined) {
    n = shown.length;
    shown.push({ key, args });
    numbers.set(sig, n);
  }
  return START + encode(n) + SEP + text + END;
}

const MARKS = new RegExp(`${START}(?:${DIGITS.join("|")})*${SEP}|${END}`, "g");

/** The text without its markers. */
export const strip = (s: string) => s.replace(MARKS, "");

export const hasMarks = (s: string) => s.includes(START) || s.includes(END);

/** A message's place in a string: [start, end) take in its markers; its text is [textStart, textEnd). */
export type Span = {
  n: number;
  start: number;
  textStart: number;
  textEnd: number;
  end: number;
  inner: Span[];
};

/** The messages in a string, outermost first, each with the ones inside it. */
export function spans(s: string): Span[] {
  const top: Span[] = [];
  const open: Span[] = [];
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === START) {
      let j = i + 1;
      let n = 0;
      for (let d = DIGITS.indexOf(s[j] ?? ""); d >= 0; d = DIGITS.indexOf(s[++j] ?? "")) n = n * 4 + d;
      if (s[j] !== SEP) continue;
      const span: Span = { n, start: i, textStart: j + 1, textEnd: -1, end: -1, inner: [] };
      (open[open.length - 1]?.inner ?? top).push(span);
      open.push(span);
      i = j;
    } else if (c === END) {
      const span = open.pop();
      if (span) {
        span.textEnd = i;
        span.end = i + 1;
      }
    }
  }
  return top;
}

/** The messages around one place in a string, innermost first. */
export function around(s: string, offset: number): Span[] {
  const out: Span[] = [];
  let level = spans(s);
  for (;;) {
    const hit = level.find((sp) => sp.start <= offset && offset < Math.max(sp.end, sp.start + 1));
    if (!hit) return out.reverse();
    out.push(hit);
    level = hit.inner;
  }
}

/** Every span, at any depth. */
export function allSpans(s: string): Span[] {
  const out: Span[] = [];
  const walk = (xs: Span[]) => {
    for (const x of xs) {
      out.push(x);
      walk(x.inner);
    }
  };
  walk(spans(s));
  return out;
}
