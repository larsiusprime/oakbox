import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { clearUndo, onUndo, type UndoOffer } from "../lib/undo";
import { t } from "../wording";

const SHOWN_MS = 6000;

/** "Removed parks · Undo" at the bottom of the window for a few seconds after a remove (lib/undo.ts). */
export function UndoToast() {
  const [offer, setOffer] = useState<UndoOffer | null>(null);
  useEffect(() => onUndo(setOffer), []);
  useEffect(() => {
    if (!offer) return;
    const timer = setTimeout(clearUndo, SHOWN_MS);
    return () => clearTimeout(timer);
  }, [offer]);
  if (!offer) return null;
  return (
    <div className="undo-toast" role="status">
      <span>{offer.text}</span>
      <Button
        className="button button-small"
        onPress={() => {
          clearUndo();
          offer.restore();
        }}
      >
        {t.buttons.undo}
      </Button>
    </div>
  );
}
