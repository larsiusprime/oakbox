import type { ReactNode } from "react";
import { t } from "../wording";
import { CloseButton } from "./Buttons";
import { RemoveButton } from "./RemoveButton";

/** A file's own name (`parcels.csv`), set off like code wherever it appears: in an entry, a list, a dropdown's
 * note or a sentence. Cut short when long; the whole name (or its path) on hover. */
export function FileName({ filename, path }: { filename: string; path?: string | null }) {
  return (
    <span className="file-name" title={path ?? filename}>
      {/* Isolated, so a right-to-left box or a long path can't reorder its characters. */}
      <bdi>{filename}</bdi>
    </span>
  );
}

/** What's known of a file, said the same way everywhere: its rows, and whether it has shapes. */
export function fileFacts(file: { rows: number | null; geometry?: boolean }): string | null {
  if (file.rows === null) return file.geometry ? t.files.shapesOnly : null;
  return t.files.facts({ rows: file.rows, shapes: file.geometry ? "yes" : "no" });
}

/** A file's first line, without the outline: its name in OAK box (mono, bold), its file name, its facts. For
 * read-only lists and choices (what runs, a choice of files, a dropdown). */
export function FileLine({
  name,
  filename,
  path,
  facts,
  children,
}: {
  name?: string | null;
  filename: string;
  path?: string | null;
  facts?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <span className="file-line">
      {name && <span className="file-label">{name}</span>}
      <FileName filename={filename} {...(path !== undefined ? { path } : {})} />
      {facts && <span className="file-facts">· {facts}</span>}
      {children}
    </span>
  );
}

/** A file wherever one is added, picked or used (the style guide, docs/style-guide.html): a thin outline; its first
 * line its name, file name, facts and status, then other actions, then the red − at the right edge (centred on a
 * one-line entry, top right on a tall one). What's set on the file goes in its body, inside the same outline. */
export function FileEntry({
  name,
  filename,
  path,
  facts,
  status,
  actions,
  onRemove,
  undo,
  onClose,
  closeLabel,
  children,
}: {
  name?: string | null;
  filename: string;
  path?: string | null;
  facts?: ReactNode;
  /** A short check on the file itself, after its facts. */
  status?: ReactNode;
  /** Other actions, as icon buttons, before the ✕. */
  actions?: ReactNode;
  /** Takes the file off its step (the red −), and `undo` puts it back. */
  onRemove?: () => void;
  undo?: () => void;
  /** Instead of removing: closes an entry that isn't saved yet (the import form): a grey ✕. */
  onClose?: () => void;
  closeLabel?: string;
  children?: ReactNode;
}) {
  return (
    <section className="entry">
      <div className="entry-head">
        <FileLine
          name={name ?? null}
          filename={filename}
          {...(path !== undefined ? { path } : {})}
          facts={facts}
        >
          {status}
        </FileLine>
        {(actions || onRemove || onClose) && (
          <span className="entry-acts">
            {actions}
            {onRemove && (
              <RemoveButton what={name ?? filename} onPress={onRemove} {...(undo ? { undo } : {})} />
            )}
            {onClose && <CloseButton {...(closeLabel ? { label: closeLabel } : {})} onPress={onClose} />}
          </span>
        )}
      </div>
      {children && <div className="entry-body">{children}</div>}
    </section>
  );
}

/** Where a file will go, before there is one: a dashed outline round the ways to add it. */
export function FileSlot({ children }: { children: ReactNode }) {
  return <div className="entry entry-slot">{children}</div>;
}

/** Something inside a file's body that can be taken away on its own (an ID): its own small box on the body's
 * columns, the ✕ at its right. Its siblings in the same list get one too, without the ✕. */
export function SubEntry({
  label,
  control,
  after,
  what,
  onRemove,
  undo,
  onClose,
}: {
  label: ReactNode;
  control: ReactNode;
  after?: ReactNode;
  /** What the red − removes ("2nd ID"), and how to put it back. */
  what?: string;
  onRemove?: () => void;
  undo?: (() => void) | undefined;
  /** A row not saved yet: a grey ✕ closes it. */
  onClose?: () => void;
}) {
  return (
    <div className="entry-sub">
      <div className="wiz-label">{label}</div>
      {control}
      <div className="entry-sub-end">
        <div className="entry-sub-after">{after}</div>
        {onRemove && what && <RemoveButton what={what} onPress={onRemove} {...(undo ? { undo } : {})} />}
        {onClose && <CloseButton onPress={onClose} />}
      </div>
    </div>
  );
}
