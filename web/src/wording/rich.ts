/** Formatting in the wording (SPEC §6.6): **bold** and *italic*; \* is an asterisk. A message with any unescaped
 * asterisk is "rich": it renders as React nodes, not a string, and its type in wording.gen.ts says so (ReactNode), so
 * it can't end up where only text goes (a title, a placeholder, a label attribute). */
import { createElement, Fragment, type ReactNode } from "react";

/** An unescaped asterisk: the same test as scripts/wording-types.mjs. */
export const RICH = /(^|[^\\])\*/;

export const isRich = (source: string) => RICH.test(source);

/** \* back to *, in a message with no formatting. */
export const plainText = (s: string) => s.replace(/\\\*/g, "*");

/** An argument's own asterisks are text, not formatting (a file name, a pattern). */
export function escapeArgs(args: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(args).map(([k, v]) => [k, typeof v === "string" ? v.replace(/\*/g, "\\*") : v]),
  );
}

/** The text with ** and * made into <strong> and <em>; `wrap` is applied to each piece of text (the live editor
 * marks each one, so a click anywhere in the message finds it). An unclosed ** or * stays as written. */
export function rich(text: string, wrap: (s: string) => string = (s) => s): ReactNode {
  type Open = { tag: "strong" | "em"; kids: ReactNode[] };
  const root: ReactNode[] = [];
  const stack: Open[] = [];
  let buf = "";
  let key = 0;
  const here = () => stack[stack.length - 1]?.kids ?? root;
  const flush = () => {
    if (buf) here().push(wrap(buf));
    buf = "";
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "\\" && text[i + 1] === "*") {
      buf += "*";
      i++;
      continue;
    }
    if (c !== "*") {
      buf += c;
      continue;
    }
    const tag = text[i + 1] === "*" ? "strong" : "em";
    if (tag === "strong") i++;
    flush();
    const top = stack[stack.length - 1];
    if (top?.tag === tag) {
      stack.pop();
      here().push(createElement(tag, { key: key++ }, ...top.kids));
    } else stack.push({ tag, kids: [] });
  }
  flush();
  while (stack.length) {
    const top = stack.pop() as Open;
    here().push(wrap(top.tag === "strong" ? "**" : "*"), ...top.kids);
  }
  return createElement(Fragment, null, ...root);
}
