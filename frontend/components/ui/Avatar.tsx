"use client";

import { cn } from "@/lib/cn";

/**
 * Plain <img>: avatars come from GitHub and the seed's avatar service, and
 * next/image would need each of those hosts allow-listed for no real benefit.
 */
export function Avatar({
  src,
  name,
  size = 32,
  className,
}: {
  src?: string;
  name: string;
  size?: number;
  className?: string;
}) {
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  if (!src) {
    return (
      <span
        className={cn(
          "inline-flex shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent",
          className,
        )}
        style={{ width: size, height: size }}
        aria-hidden
      >
        {initials || "?"}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className={cn("shrink-0 rounded-full border border-border object-cover", className)}
      style={{ width: size, height: size }}
    />
  );
}
