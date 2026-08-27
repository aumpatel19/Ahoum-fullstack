"use client";

import { CalendarPlus, Pencil, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/AuthGuard";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatPrice } from "@/lib/format";
import { useCreatorSessions, useDeleteSession } from "@/lib/queries";
import type { CreatorSession } from "@/types/api";

function statusFor(session: CreatorSession) {
  if (!session.is_active) return { tone: "neutral" as const, label: "Removed" };
  if (session.has_started) return { tone: "neutral" as const, label: "Past" };
  if (session.is_sold_out) return { tone: "danger" as const, label: "Sold out" };
  return { tone: "success" as const, label: "Open" };
}

function CreatorContent() {
  const { data, isLoading, isError, refetch } = useCreatorSessions();
  const remove = useDeleteSession();
  const [pendingDelete, setPendingDelete] = useState<CreatorSession | null>(null);

  const sessions = data?.results ?? [];

  function confirmDelete() {
    if (!pendingDelete) return;
    remove.mutate(pendingDelete.id, {
      onSuccess: () => {
        toast.success("Session removed from the catalogue.");
        setPendingDelete(null);
      },
      onError: (error) => {
        toast.error(errorMessage(error, "Couldn't remove that session."));
        setPendingDelete(null);
      },
    });
  }

  return (
    <>
      <PageHeader
        title="Creator dashboard"
        subtitle="Your sessions and how they're filling up."
        action={
          <Link href="/creator/sessions/new">
            <Button icon={<CalendarPlus className="h-4 w-4" />}>New session</Button>
          </Link>
        }
      />

      <div className="page mt-8">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-20 w-full rounded-2xl" />
            ))}
          </div>
        ) : isError ? (
          <EmptyState
            icon={<Users className="h-5 w-5" />}
            title="Couldn't load your sessions"
            description="The API didn't answer."
            action={<Button onClick={() => refetch()}>Try again</Button>}
          />
        ) : sessions.length === 0 ? (
          <EmptyState
            icon={<CalendarPlus className="h-5 w-5" />}
            title="No sessions yet"
            description="Publish your first session and it will show up in the public catalogue straight away."
            action={
              <Link href="/creator/sessions/new">
                <Button>Create a session</Button>
              </Link>
            }
          />
        ) : (
          <Card className="divide-y divide-border/70 overflow-hidden">
            <div className="hidden grid-cols-12 gap-4 px-5 py-3 text-xs font-medium uppercase tracking-wide text-muted sm:grid">
              <span className="col-span-5">Session</span>
              <span className="col-span-3">Starts</span>
              <span className="col-span-2">Booked</span>
              <span className="col-span-2 text-right">Actions</span>
            </div>

            {sessions.map((session) => {
              const status = statusFor(session);
              return (
                <div
                  key={session.id}
                  className="grid grid-cols-1 gap-3 px-5 py-4 transition hover:bg-elevated/40 sm:grid-cols-12 sm:items-center sm:gap-4"
                >
                  <div className="sm:col-span-5">
                    <Link
                      href={`/sessions/${session.id}`}
                      className="font-medium text-content transition hover:text-accent"
                    >
                      {session.title}
                    </Link>
                    <p className="mt-1 flex items-center gap-2 text-xs text-muted">
                      <Badge tone={status.tone}>{status.label}</Badge>
                      {formatPrice(session.price)}
                    </p>
                  </div>

                  <span className="text-sm text-muted sm:col-span-3">
                    {formatDateTime(session.starts_at)}
                  </span>

                  <span className="text-sm sm:col-span-2">
                    <span className="font-medium text-content">{session.confirmed_bookings}</span>
                    <span className="text-muted"> / {session.capacity}</span>
                  </span>

                  <div className="flex gap-2 sm:col-span-2 sm:justify-end">
                    <Link href={`/creator/sessions/${session.id}/edit`}>
                      <Button variant="secondary" size="sm" icon={<Pencil className="h-3.5 w-3.5" />}>
                        Edit
                      </Button>
                    </Link>
                    {session.is_active ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Remove ${session.title}`}
                        onClick={() => setPendingDelete(session)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </Card>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Remove this session?"
        description="It disappears from the public catalogue. Existing bookings keep their history, which is why this is a soft delete."
        confirmLabel="Remove"
        loading={remove.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}

export default function CreatorPage() {
  return (
    <AuthGuard requireCreator>
      <CreatorContent />
    </AuthGuard>
  );
}
