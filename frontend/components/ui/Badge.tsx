import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Tone = "neutral" | "accent" | "success" | "warn" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "border-border bg-elevated text-muted",
  accent: "border-accent/40 bg-accent/10 text-accent",
  success: "border-success/30 bg-success/10 text-success",
  warn: "border-warn/30 bg-warn/10 text-warn",
  danger: "border-danger/30 bg-danger/10 text-danger",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
