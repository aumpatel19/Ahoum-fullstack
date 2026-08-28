import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden">
      <div className="aurora absolute inset-0" aria-hidden />
      {/* Fades the header into the page instead of ending it on a hard rule. */}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-border to-transparent"
        aria-hidden
      />

      <div className="page relative flex flex-col gap-5 py-10 sm:flex-row sm:items-end sm:justify-between sm:py-12">
        <div>
          {eyebrow ? (
            <p className="mb-3 text-xs font-medium uppercase tracking-looser text-accent-soft">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-3xl font-semibold leading-[1.1] sm:text-4xl">{title}</h1>
          {subtitle ? (
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">{subtitle}</p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}
