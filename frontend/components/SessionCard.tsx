import { Clock } from "lucide-react";
import Link from "next/link";

import { SeatsPill } from "@/components/SeatsPill";
import { Avatar } from "@/components/ui/Avatar";
import { dateParts, formatDuration, formatPrice } from "@/lib/format";
import type { Session } from "@/types/api";

export function SessionCard({ session }: { session: Session }) {
  const when = dateParts(session.starts_at);

  return (
    <Link
      href={`/sessions/${session.id}`}
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-surface bg-surface-sheen p-5
                 shadow-card transition duration-300 ease-out
                 hover:-translate-y-1 hover:border-accent/40 hover:shadow-lifted"
    >
      {/* A violet wash that only appears on hover. The lit-from-above sheen is a
          background layer (bg-surface-sheen), so it can never cover content. */}
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-accent/[0.09] via-transparent to-transparent
                   opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        aria-hidden
      />

      <div className="relative flex items-start justify-between gap-3">
        {/* The date is the thing people scan for, so it gets a shape of its own. */}
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl border border-border bg-elevated">
            <span className="text-[10px] font-medium uppercase tracking-looser text-muted">
              {when.month}
            </span>
            <span className="text-base font-semibold leading-none text-content">{when.day}</span>
          </div>
          <div className="text-xs leading-snug text-muted">
            <div className="font-medium text-content/80">{when.weekday}</div>
            <div>{when.time}</div>
          </div>
        </div>
        <SeatsPill session={session} />
      </div>

      <h3 className="relative mt-4 text-lg font-semibold leading-snug text-content transition-colors group-hover:text-accent-soft">
        {session.title}
      </h3>
      <p className="relative mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">
        {session.description}
      </p>

      <div className="relative mt-5 flex items-end justify-between border-t hairline pt-4">
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted">
          <Avatar src={session.creator.avatar_url} name={session.creator.display_name} size={22} />
          <span className="truncate">{session.creator.display_name}</span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          <span className="flex items-center gap-1 text-xs text-muted">
            <Clock className="h-3.5 w-3.5" />
            {formatDuration(session.duration_minutes)}
          </span>
          <span className="text-sm font-semibold tabular-nums text-teal">
            {formatPrice(session.price)}
          </span>
        </span>
      </div>
    </Link>
  );
}
