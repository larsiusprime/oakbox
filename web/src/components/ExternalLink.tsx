import { ExternalLink as Out } from "lucide-react";
import type { ReactNode } from "react";

/** A link that leaves the app (opens in the browser): a link, with a small ↗ so it's clear it goes elsewhere. */
export function ExternalLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      className={className ? `link-out ${className}` : "link-out"}
      href={href}
      target="_blank"
      rel="noreferrer"
    >
      {children}
      <Out aria-hidden="true" size="0.85em" className="link-out-icon" />
    </a>
  );
}
