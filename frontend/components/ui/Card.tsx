import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        // bg-surface paints the colour, bg-surface-sheen layers a top-down
        // highlight over it - no overlay element, so nothing can cover content.
        "relative overflow-hidden rounded-2xl border border-border bg-surface bg-surface-sheen shadow-card",
        className,
      )}
      {...rest}
    />
  );
}
