import { Info } from "lucide-react";
import type { ReactElement } from "react";
import { Focusable, OverlayArrow, Tooltip, TooltipTrigger } from "react-aria-components";

/** Help on hover and keyboard focus, instead of text on the screen (SPEC D42). */
export function Tip({ text, children }: { text: string; children: ReactElement }) {
  return (
    <TooltipTrigger delay={400} closeDelay={100}>
      {children}
      <Tooltip className="tooltip" offset={8}>
        <OverlayArrow className="tooltip-arrow">
          <svg width={10} height={6} viewBox="0 0 10 6" aria-hidden="true">
            <path d="M0 0 L5 6 L10 0" />
          </svg>
        </OverlayArrow>
        {text}
      </Tooltip>
    </TooltipTrigger>
  );
}

/** A tooltip on something that isn't a button, such as a disabled button or a read-only value. */
export function TipOn({
  text,
  className,
  children,
}: {
  text: string;
  className?: string;
  children: ReactElement;
}) {
  return (
    <Tip text={text}>
      <Focusable>
        <span className={className ?? "tip-target"}>{children}</span>
      </Focusable>
    </Tip>
  );
}

/** A short phrase with an ⓘ: the fuller explanation on hover or keyboard focus (AGENTS.md: short labels, the rest
 * on demand). */
export function InfoTip({ label, text }: { label: string; text: string }) {
  return (
    <Tip text={text}>
      <Focusable>
        <span className="info-tip">
          {label}
          <Info aria-hidden="true" size="0.85em" className="info-tip-icon" />
        </span>
      </Focusable>
    </Tip>
  );
}
