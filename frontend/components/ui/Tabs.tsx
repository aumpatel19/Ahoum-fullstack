"use client";

import { cn } from "@/lib/cn";

export function Tabs<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div role="tablist" className="inline-flex rounded-xl border border-border bg-surface p-1">
      {options.map((option) => (
        <button
          key={option.value}
          role="tab"
          aria-selected={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "rounded-lg px-4 py-1.5 text-sm font-medium transition",
            value === option.value
              ? "bg-elevated text-content"
              : "text-muted hover:text-content",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
