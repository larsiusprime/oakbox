import { Minus } from "lucide-react";
import type { ReactNode } from "react";
import { Button, type ButtonProps } from "react-aria-components";
import { offerUndo } from "../lib/undo";
import { t } from "../wording";
import { Tip } from "./Tip";

/** The one way to take something off a list or a step (a file from a step, an ID, a test, a field, a model…): a red
 * button with a white − (the pair of AddButton's +), raised and pressed like every button, last on its line at the
 * right edge. Its label ("Remove parks") shows on hover and is read aloud. With `undo`, the remove can be taken back:
 * "Removed parks · Undo" shows for a few seconds (components/UndoToast.tsx).
 * Deleting for good is not this: a danger button with a trash can and its words, which asks first (DeleteButton).
 * Closing a popup is not this either (CloseButton, a grey ✕). */
export function RemoveButton({
  what,
  label,
  undo,
  onPress,
  ...props
}: Omit<ButtonProps, "className" | "children" | "aria-label" | "onPress"> & {
  /** What it removes, in a few words: "parks", "2nd ID". */
  what: string;
  /** Instead of "Remove {what}", where that reads badly. */
  label?: string;
  onPress: () => void;
  /** Puts it back. */
  undo?: () => void;
}) {
  const name = label ?? t.buttons.remove({ what });
  return (
    <Tip text={name}>
      <Button
        {...props}
        className="remove-x"
        aria-label={name}
        onPress={() => {
          onPress();
          if (undo) offerUndo(t.buttons.removed({ what }), undo);
        }}
      >
        <Minus aria-hidden="true" size="1em" strokeWidth={3.5} />
      </Button>
    </Tip>
  );
}

/** Taking something away, with words ("− Remove group"): the same red button as RemoveButton, its white − then its
 * words. What it calls offers Undo itself (lib/undo.ts), as it knows how to put it back. Told apart from deleting
 * (DeleteButton) by its symbol: − here, a trash can there. */
export function RemoveTextButton({
  children,
  small = false,
  ...props
}: Omit<ButtonProps, "className" | "children"> & { children: ReactNode; small?: boolean }) {
  return (
    <Button {...props} className={small ? "button button-small button-danger" : "button button-danger"}>
      <Minus aria-hidden="true" size="1em" strokeWidth={3} />
      {children}
    </Button>
  );
}
