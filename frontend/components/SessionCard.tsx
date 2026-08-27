import { Clock, UserRound } from "lucide-react";
import Link from "next/link";

import { SeatsPill } from "@/components/SeatsPill";
import { Avatar } from "@/components/ui/Avatar";
import { formatDateTime, formatDuration, formatPrice } from "@/lib/format";
import type { Session } from "@/types/api";

export function SessionCard({ session }: { session: Session }) {
  return (
    <Link
      href={`/sessions/${session.id}`}
      className="group flex flex-col rounded-2xl border border-border bg-surface p-5 shadow-card transition hover:-translate-y-0.5 hover:border-accent/50"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">
          {formatDateTime(session.starts_at)}
        </span>
        <SeatsPill session={session} />
      </div>

      <h3 className="mt-3 text-lg font-semibold leading-snug text-content group-hover:text-accent">
        {session.title}
      </h3>
      <p className="mt-1.5 line-clamp-2 text-sm text-muted">{session.description}</p>

      <div className="mt-5 flex items-center justify-between border-t border-border/70 pt-4">
        <span className="flex items-center gap-2 text-xs text-muted">
          <Avatar src={session.creator.avatar_url} name={session.creator.display_name} size={22} />
          {session.creator.display_name}
        </span>
        <span className="flex items-center gap-3 text-xs text-muted">
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {formatDuration(session.duration_minutes)}
          </span>
          <span className="flex items-center gap-1 font-medium text-content">
            <UserRound className="h-3.5 w-3.5 text-muted" />
            {formatPrice(session.price)}
          </span>
        </span>
      </div>
    </Link>
  );
}
