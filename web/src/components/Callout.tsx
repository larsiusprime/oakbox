/** A long explanation folded behind a ⚠ (or ⓘ) and its first sentence: the reader opens it if they want it,
 * and folds it away again. Short notes stay plain text; this is for paragraphs. */
import { ChevronDown, ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "react-aria-components";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import { t } from "../wording";

export function Callout({
  summary,
  children,
  tone = "warn",
}: {
  /** What it's about, in a line: shown folded and open. */
  summary: ReactNode;
  children: ReactNode;
  tone?: "warn" | "info";
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`callout callout-${tone}${open ? " open" : ""}`}>
      <Button className="callout-toggle" aria-expanded={open} onPress={() => setOpen(!open)}>
        {tone === "warn" ? (
          <img src={warningIcon} alt="" className="callout-icon" />
        ) : (
          <span className="callout-icon" aria-hidden="true">
            ⓘ
          </span>
        )}
        <span className="callout-summary">{summary}</span>
        <span className="callout-more">{open ? t.callout.hide : t.callout.show}</span>
        {open ? (
          <ChevronDown aria-hidden="true" size="1em" className="callout-chev" />
        ) : (
          <ChevronRight aria-hidden="true" size="1em" className="callout-chev" />
        )}
      </Button>
      {open && <div className="callout-body">{children}</div>}
    </div>
  );
}

/** A text's first sentence (to its first ". "), for a callout's summary line. */
export function firstSentence(text: string): string {
  const i = text.search(/[.!?:](\s|$)/);
  return i < 0 ? text : text.slice(0, i + 1);
}
