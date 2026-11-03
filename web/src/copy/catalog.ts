/** The UI's copy (SPEC §6.6), imported from "copy" (index.ts): every message is in en.json, in ICU MessageFormat, with its types in copy.gen.ts
 * (npm run copy:types). A message with no arguments is a string; one with arguments is a function of an object of
 * them, `t.x.plusOthers({ first, n })`. Wording that needs code first (joining a list, changing case, arithmetic)
 * goes through `say` (logic.ts), which works out the arguments and formats the message. */
import { IntlMessageFormat } from "intl-messageformat";
import type { Copy } from "./copy.gen";
import catalog from "./en.json";

export type { Copy };

// Numbers as the user's own locale writes them (as toLocaleString() does).
const locale = new Intl.NumberFormat().resolvedOptions().locale;
// No braces and no apostrophes: the message is its own text.
const PLAIN = /^[^{}']*$/;

type Args = Record<string, unknown>;

function message(source: string): string | ((args: Args) => string) {
  if (PLAIN.test(source)) return source;
  // `ignoreTag`: copy has angle brackets (<surname>) that aren't markup.
  const format = new IntlMessageFormat(source, locale, undefined, { ignoreTag: true });
  const literal = format.getAst().every((e) => e.type === 0 /* literal */);
  if (literal) return format.format() as string;
  return (args: Args) => format.format(args) as string;
}

function build(value: unknown): unknown {
  if (typeof value === "string") return message(value);
  if (Array.isArray(value)) return value.map(build);
  if (value && typeof value === "object")
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, build(v)]));
  return value;
}

export const t = build(catalog) as Copy;

/** A major step's landing page (SPEC D21): what it's for, before its first part. */
export type Landing = {
  kicker: string;
  title: string;
  lede: string;
  happens: string[];
  decide: string[];
  end: string[];
  needs: string;
};
