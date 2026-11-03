import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import { Button, type ButtonProps } from "react-aria-components";

/** The one way to add something (a file, a field, a test, a group, a step…): a button with a plus, its words
 * "Add …" without a "+" of their own. It opens what it adds (a menu, a popover, a new row) or adds it at once. */
export function AddButton({
  children,
  primary = false,
  ...props
}: Omit<ButtonProps, "className" | "children"> & { children: ReactNode; primary?: boolean }) {
  return (
    <Button {...props} className={primary ? "button button-primary add-button" : "button add-button"}>
      <Plus aria-hidden="true" size="1em" />
      {children}
    </Button>
  );
}
