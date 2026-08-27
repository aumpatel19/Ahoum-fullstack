import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="aurora border-b border-border/70">
      <div className="page flex flex-col gap-4 py-10 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
          {subtitle ? <p className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</p> : null}
        </div>
        {action}
      </div>
    </div>
  );
}
