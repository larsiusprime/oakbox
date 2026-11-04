import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Button, type ButtonProps } from "react-aria-components";

/** Unfolds something in place: a chevron (▸, ▾ when open) before its words, never a link or a bare word. */
export function Disclose({
  open,
  className,
  children,
  ...props
}: Omit<ButtonProps, "className" | "children" | "aria-expanded"> & {
  open: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Button {...props} className={className ? `disclose ${className}` : "disclose"} aria-expanded={open}>
      <ChevronRight aria-hidden="true" size="1em" className="disclose-icon" />
      {children}
    </Button>
  );
}
