import { X } from "lucide-react";
import { Button, type ButtonProps } from "react-aria-components";

/** The one way to take something away (a file from a step, an ID, a test, a field, a model…): a red ✕, last on its
 * line at the right edge, its label saying what it removes. Never a "Remove" link, "(remove)" or a grey X.
 * Deleting from disk (a whole project) is not this: it keeps its own button and confirmation. */
export function RemoveButton({
  label,
  ...props
}: Omit<ButtonProps, "className" | "children" | "aria-label"> & { label: string }) {
  return (
    <Button {...props} className="remove-x" aria-label={label}>
      <X aria-hidden="true" size="1em" />
    </Button>
  );
}
