/** A value from a file, cut short when it's long (the whole of it on hover): values can be hundreds of characters
 * with no space, and one of them shouldn't stretch a table, a list or a dialog. */

import { short } from "../lib/format";

export function Val({ v, max = 40 }: { v: string | number | null | undefined; max?: number }) {
  if (v === null || v === undefined) return null;
  const text = String(v);
  const cut = short(text, max);
  return cut === text ? text : <span title={text}>{cut}</span>;
}
