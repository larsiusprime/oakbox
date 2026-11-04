/** Undo, after a remove (style guide: "a remove can be undone"): the last remove's words and how to put it back,
 * shown for a few seconds by components/UndoToast.tsx. One at a time: a new remove replaces the offer. */
export type UndoOffer = { text: string; restore: () => void };

let current: UndoOffer | null = null;
const listeners = new Set<(o: UndoOffer | null) => void>();

export function offerUndo(text: string, restore: () => void) {
  current = { text, restore };
  for (const l of listeners) l(current);
}

export function clearUndo() {
  current = null;
  for (const l of listeners) l(null);
}

export function onUndo(listener: (o: UndoOffer | null) => void): () => void {
  listeners.add(listener);
  listener(current);
  return () => listeners.delete(listener);
}
