import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import { Button, type ButtonProps } from "react-aria-components";

/** The one way to add something (a file, a field, a test, a group, a step…): a button with a plus, its words
 * "Add …" without a "+" of their own. It opens what it adds (a menu, a popover, a new row) or adds it at once.
 * end: it comes after the list it adds to, at that list's right edge (outside any frame); a row of buttons after a
 * list is `.add-row` instead. */
export function AddButton({
  children,
  primary = false,
  end = false,
  ...props
}: Omit<ButtonProps, "className" | "children"> & { children: ReactNode; primary?: boolean; end?: boolean }) {
  const classes = ["button", primary ? "button-primary" : "", "add-button", end ? "add-end" : ""];
  return (
    <Button {...props} className={classes.filter(Boolean).join(" ")}>
      <Plus aria-hidden="true" size="1em" />
      {children}
    </Button>
  );
}
