/** A figure judged against a target: met, near it, or missed. */
export type Verdict = "ok" | "slight" | "bad";

const GLYPH: Record<Verdict, string> = { ok: "✓", slight: "~", bad: "✗" };

export function verdictOf(ok: boolean | null | undefined): Verdict | null {
  return ok == null ? null : ok ? "ok" : "bad";
}

/** The one pill every judged figure wears: ✓ green, ~ amber, ✗ red; a word after it if given. Without a verdict, a
 * grey pill with the word, or nothing. */
export function Pill({
  v,
  label,
  title,
}: {
  v: Verdict | null | undefined;
  label?: string | undefined;
  title?: string | undefined;
}) {
  if (!v)
    return label ? (
      <span className="rv-pill rv-few" title={title}>
        {label}
      </span>
    ) : null;
  return (
    <span className={`rv-pill rv-${v}`} title={title}>
      {GLYPH[v]}
      {label ? ` ${label}` : ""}
    </span>
  );
}
