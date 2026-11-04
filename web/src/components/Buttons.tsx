import { Trash2, X } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button, type ButtonProps, Dialog, DialogTrigger, Popover } from "react-aria-components";
import { t } from "../wording";
import { Tip } from "./Tip";

/* The button family beside .button, .button-primary, AddButton and RemoveButton (style guide, section 1). Every
   one is raised and sinks when pressed: an action looks like a button. */

type Base = Omit<ButtonProps, "className" | "children">;

/** An action beside a line of text: after a check ("Reconcile…"), inside a row ("See rows"), "Options ˅". The same
 * bevel as .button, smaller. */
export function SmallButton({ children, ...props }: Base & { children: ReactNode }) {
  return (
    <Button {...props} className="button button-small">
      {children}
    </Button>
  );
}

/** An icon action: a raised square (show the map, move up, show it larger). With `pressed`, a toggle that stays
 * pressed in while it's on. Its label shows on hover and is read aloud. */
export function ToolButton({
  label,
  pressed,
  children,
  ...props
}: Omit<Base, "aria-label" | "aria-pressed"> & { label: string; pressed?: boolean; children: ReactNode }) {
  return (
    <Tip text={label}>
      <Button
        {...props}
        className="tool-button"
        aria-label={label}
        {...(pressed !== undefined ? { "aria-pressed": pressed } : {})}
      >
        {children}
      </Button>
    </Tip>
  );
}

/** Closes a popup, a panel or a dialog: a grey ✕, only at its top right. Nothing is lost (never for removing). */
export function CloseButton({ label, ...props }: Omit<Base, "aria-label"> & { label?: string }) {
  const name = label ?? t.buttons.close;
  return (
    <Tip text={name}>
      <Button {...props} className="close-x" aria-label={name}>
        <X aria-hidden="true" size="1em" strokeWidth={2.4} />
      </Button>
    </Tip>
  );
}

/** Deletes for good: a danger button with a trash can and its words. It asks first, in a popover beside it:
 * `confirm` says what will be lost, then [🗑 Delete] [Cancel]. */
export function DeleteButton({
  children,
  confirm,
  onDelete,
  isDisabled,
}: {
  children: ReactNode;
  confirm: string;
  onDelete: () => void;
  isDisabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <DialogTrigger isOpen={open} onOpenChange={setOpen}>
      <Button className="button button-danger" {...(isDisabled ? { isDisabled } : {})}>
        <Trash2 aria-hidden="true" size="1em" />
        {children}
      </Button>
      <Popover className="popover" placement="bottom end">
        <Dialog className="popover-body confirm-pop" role="alertdialog" aria-label={confirm}>
          <p>{confirm}</p>
          <div className="form-actions">
            <Button
              className="button button-danger"
              onPress={() => {
                setOpen(false);
                onDelete();
              }}
            >
              <Trash2 aria-hidden="true" size="1em" />
              {t.buttons.delete}
            </Button>
            <Button className="button" autoFocus onPress={() => setOpen(false)}>
              {t.buttons.cancel}
            </Button>
          </div>
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}
