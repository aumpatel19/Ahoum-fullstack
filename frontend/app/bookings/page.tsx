"use client";

import { CalendarX, Clock } from "lucide-react";
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
import { Tabs } from "@/components/ui/Tabs";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatDuration, formatPrice, relativeTime } from "@/lib/format";
import { useCancelBooking, useMyBookings } from "@/lib/queries";
import type { Booking } from "@/types/api";

type Scope = "active" | "past";

function BookingRow({ booking, onCancel }: { booking: Booking; onCancel?: () => void }) {
  const { session } = booking;
  return (
    <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/sessions/${session.id}`}
            className="font-medium text-content transition hover:text-accent"
          >
            {session.title}
          </Link>
          {booking.status === "CANCELLED" ? (
            <Badge tone="danger">Cancelled</Badge>
          ) : session.has_started ? (
            <Badge tone="neutral">Completed</Badge>
          ) : (
            <Badge tone="success">Confirmed</Badge>
          )}
        </div>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {formatDateTime(session.starts_at)} · {formatDuration(session.duration_minutes)}
          </span>
          <span>{formatPrice(session.price)}</span>
          <span>with {session.creator.display_name}</span>
        </p>
      </div>

      {onCancel ? (
        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden text-xs text-muted sm:inline">
            starts {relativeTime(session.starts_at)}
          </span>
          <Button variant="secondary" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function BookingsContent() {
  const [scope, setScope] = useState<Scope>("active");
  const { data, isLoading, isError, refetch } = useMyBookings(scope);
  const cancel = useCancelBooking();
  const [pendingCancel, setPendingCancel] = useState<Booking | null>(null);

  const bookings = data?.results ?? [];

  function confirmCancel() {
    if (!pendingCancel) return;
    cancel.mutate(pendingCancel.id, {
      onSuccess: () => {
        toast.success("Booking cancelled.");
        setPendingCancel(null);
      },
      onError: (error) => {
        toast.error(errorMessage(error, "Couldn't cancel that booking."));
        setPendingCancel(null);
      },
    });
  }

  return (
    <>
      <PageHeader title="My bookings" subtitle="Everything you've reserved, past and present." />

      <div className="page mt-8">
        <Tabs<Scope>
          value={scope}
          onChange={setScope}
          options={[
            { value: "active", label: "Active" },
            { value: "past", label: "Past" },
          ]}
        />

        <div className="mt-6 space-y-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-2xl" />
            ))
          ) : isError ? (
            <EmptyState
              icon={<CalendarX className="h-5 w-5" />}
              title="Couldn't load your bookings"
              description="The API didn't answer."
              action={<Button onClick={() => refetch()}>Try again</Button>}
            />
          ) : bookings.length === 0 ? (
            <EmptyState
              icon={<CalendarX className="h-5 w-5" />}
              title={scope === "active" ? "No upcoming bookings" : "Nothing in your history yet"}
              description={
                scope === "active"
                  ? "When you book a session it will appear here."
                  : "Sessions you've attended or cancelled will collect here."
              }
              action={
                scope === "active" ? (
                  <Link href="/">
                    <Button>Browse sessions</Button>
                  </Link>
                ) : undefined
              }
            />
          ) : (
            bookings.map((booking) => (
              <BookingRow
                key={booking.id}
                booking={booking}
                onCancel={
                  booking.status === "CONFIRMED" && !booking.session.has_started
                    ? () => setPendingCancel(booking)
                    : undefined
                }
              />
            ))
          )}
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(pendingCancel)}
        title="Cancel this booking?"
        description={`"${pendingCancel?.session.title ?? ""}" will lose your seat and someone else can take it.`}
        confirmLabel="Cancel booking"
        loading={cancel.isPending}
        onConfirm={confirmCancel}
        onCancel={() => setPendingCancel(null)}
      />
    </>
  );
}

export default function BookingsPage() {
  return (
    <AuthGuard>
      <BookingsContent />
    </AuthGuard>
  );
}
