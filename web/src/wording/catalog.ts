/** The UI's wording (SPEC §6.6), imported from "wording" (index.ts): every message is in en.json, in ICU MessageFormat, with its types in wording.gen.ts
 * (npm run wording:types). A message with no arguments is a string; one with arguments is a function of an object of
 * them, `t.x.plusOthers({ first, n })`. Wording that needs code first (joining a list, changing case, arithmetic)
 * goes through `say` (logic.ts), which works out the arguments and formats the message. */
import { IntlMessageFormat } from "intl-messageformat";
import type { ReactNode } from "react";
import catalog from "./en.json";
import { mark } from "./marks";
import { escapeArgs, isRich, plainText, rich } from "./rich";
import type { Wording } from "./wording.gen";

export type { Wording };

// Numbers as the user's own locale writes them (as toLocaleString() does).
const locale = new Intl.NumberFormat().resolvedOptions().locale;
// No braces and no apostrophes: the message is its own text.
const PLAIN = /^[^{}']*$/;

type Args = Record<string, unknown>;

/** Every message's source as it is now, by key ("wizard.steps.basics.title"): the live editor reads it. */
export const sources = new Map<string, string>();

type Message = string | ReactNode | ((args: Args) => string | ReactNode);

function message(key: string, source: string): Message {
  if (__WORDING_EDIT__) return marked(key, source);
  const fancy = isRich(source);
  if (PLAIN.test(source)) return fancy ? rich(source) : plainText(source);
  // `ignoreTag`: the wording has angle brackets (<surname>) that aren't markup.
  const format = new IntlMessageFormat(source, locale, undefined, { ignoreTag: true });
  const literal = format.getAst().every((e) => e.type === 0 /* literal */);
  if (fancy) {
    if (literal) return rich(format.format() as string);
    return (args: Args) => rich(format.format(escapeArgs(args)) as string);
  }
  if (literal) return plainText(format.format() as string);
  return (args: Args) => plainText(format.format(args) as string);
}

function build(value: unknown, key: string): unknown {
  if (typeof value === "string") return message(key, value);
  if (Array.isArray(value)) return value.map((v, i) => build(v, `${key}.${i}`));
  if (value && typeof value === "object")
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, build(v, key ? `${key}.${k}` : k)]));
  return value;
}

export const t = build(catalog, "") as Wording;

// Live editing (`npm run dev:wording` only; every other build drops this): each message carries its markers, and when
// en.json changes (saved from the editor, or in a text editor) `t` is refilled in place, so what holds a part of it
// sees the new words, and the editor puts them on the screen.
function marked(key: string, source: string): Message {
  sources.set(key, source);
  let format: IntlMessageFormat;
  try {
    format = new IntlMessageFormat(source, locale, undefined, { ignoreTag: true });
  } catch (e) {
    const said = `⚠ ${key}: ${(e as Error).message}`;
    return () => mark(key, null, said);
  }
  const literal = format.getAst().every((e) => e.type === 0);
  // Formatted: each piece of text marked on its own, so a click on any of it (bold or not) finds the message.
  if (isRich(source)) {
    if (literal) return rich(format.format() as string, (s) => mark(key, null, s, true));
    return (args: Args) => rich(format.format(escapeArgs(args)) as string, (s) => mark(key, args, s, true));
  }
  if (literal) return mark(key, null, plainText(format.format() as string));
  return (args: Args) => mark(key, args, plainText(format.format(args) as string));
}

function refill(into: Record<string, unknown>, next: Record<string, unknown>, key: string) {
  for (const [k, v] of Object.entries(next)) {
    const at = key ? `${key}.${k}` : k;
    const was = into[k];
    if (
      v &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      was &&
      typeof was === "object" &&
      !Array.isArray(was)
    )
      refill(was as Record<string, unknown>, v as Record<string, unknown>, at);
    else into[k] = build(v, at);
  }
}

if (__WORDING_EDIT__ && import.meta.hot) {
  import.meta.hot.accept("./en.json", (next) => {
    if (!next) return;
    const before = new Map(sources);
    refill(t as unknown as Record<string, unknown>, next.default as Record<string, unknown>, "");
    const changed = [...sources].filter(([k, v]) => before.get(k) !== v).map(([k]) => k);
    // Formatting can't be put into text already on the screen: when a formatted message changes (or one gains or
    // loses its formatting), the app is drawn again (WordingRoot), on the same page.
    if (changed.some((k) => isRich(before.get(k) ?? "") || isRich(sources.get(k) ?? "")))
      window.dispatchEvent(new CustomEvent("oakbox-wording-redraw"));
    window.dispatchEvent(new CustomEvent("oakbox-wording-changed", { detail: changed }));
  });
}

/** A major step's landing page (SPEC D21): what it's for, in a few lines, before its first part. */
export type Landing = {
  title: string;
  // Shown, never used as text: may be formatted (**bold**, *italic*).
  lede: ReactNode;
};
