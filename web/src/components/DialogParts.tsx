/** A dialog's parts (style guide: dialogs). One sheet of paper: each thing to decide is a section, a bold heading with
 * a few words beside it, then what shows it and its choice; sections are split by one hairline, nothing boxed. The
 * result and the buttons sit on a strip at the foot. */
import type { ReactNode } from "react";

export function DialogSection({
  title,
  note,
  children,
}: {
  title: ReactNode;
  /** A few words beside the heading: what it means, how to think about it. */
  note?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="dlg-sec">
      <div className="dlg-sec-head">
        <h3>{title}</h3>
        {note && <span className="wiz-from">{note}</span>}
      </div>
      {children}
    </section>
  );
}

/** The foot: what Save will do (219,824 rows → 219,381 parcels), then the buttons, at the right. */
export function DialogFoot({ result, children }: { result?: ReactNode; children: ReactNode }) {
  return (
    <div className="dlg-foot">
      {result && <b className="dlg-result">{result}</b>}
      <span className="dlg-grow" />
      {children}
    </div>
  );
}
