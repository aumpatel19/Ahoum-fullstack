"use client";

import { ArrowLeft, CalendarDays, CheckCircle2, Clock, Info, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { SeatsPill } from "@/components/SeatsPill";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Skeleton } from "@/components/ui/Skeleton";
import { tokenStore } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatDuration, formatPrice, relativeTime } from "@/lib/format";
import { useBookSession, useCancelBooking, useMyBookings, useSession } from "@/lib/queries";

export default function SessionDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sessionId = Number(params.id);

  const { data: session, isLoading, isError } = useSession(sessionId);
  const { data: bookings } = useMyBookings("active");
  const book = useBookSession(sessionId);
  const cancel = useCancelBooking();
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const authenticated = tokenStore.isAuthenticated;
  const myBooking = bookings?.results.find((booking) => booking.session.id === sessionId);

  function onBook() {
    if (!authenticated) {
      router.push("/login?error=not_authenticated");
      return;
    }
    book.mutate(undefined, {
      onSuccess: () => toast.success("Seat booked. See you there."),
      // The API is the only source of truth about availability: this is where a
      // stale "2 seats left" turns into an honest "sold out" for the loser of a race.
      onError: (error) => toast.error(errorMessage(error, "Couldn't book that seat.")),
    });
  }

  function onCancel() {
    if (!myBooking) return;
    cancel.mutate(myBooking.id, {
      onSuccess: () => {
        toast.success("Booking cancelled. The seat is back in the pool.");
        setConfirmingCancel(false);
      },
      onError: (error) => {
        toast.error(errorMessage(error, "Couldn't cancel that booking."));
        setConfirmingCancel(false);
      },
    });
  }

  if (isLoading) {
    return (
      <div className="page max-w-3xl py-12">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-4 h-9 w-2/3" />
        <Skeleton className="mt-6 h-40 w-full" />
      </div>
    );
  }

  if (isError || !session) {
    return (
      <div className="page max-w-3xl py-20 text-center">
        <h1 className="text-xl font-semibold">Session not found</h1>
        <p className="mt-2 text-sm text-muted">It may have been removed by its creator.</p>
        <Button className="mt-6" variant="secondary" onClick={() => router.push("/")}>
          Back to catalogue
        </Button>
      </div>
    );
  }

  const bookDisabled = session.has_started || session.is_sold_out || Boolean(myBooking);
  const bookLabel = !authenticated
    ? "Sign in to book"
    : myBooking
      ? "You're booked"
      : session.has_started
        ? "This session has started"
        : session.is_sold_out
          ? "Sold out"
          : "Book a seat";

  return (
    <div className="page max-w-3xl py-10">
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-sm text-muted transition hover:text-content"
      >
        <ArrowLeft className="h-4 w-4" /> All sessions
      </Link>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <SeatsPill session={session} />
        {myBooking ? (
          <Badge tone="accent">
            <CheckCircle2 className="h-3 w-3" /> Booked
          </Badge>
        ) : null}
      </div>

      <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-tight">{session.title}</h1>

      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted">
        <span className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4" />
          {formatDateTime(session.starts_at)}
          <span className="text-muted/70">({relativeTime(session.starts_at)})</span>
        </span>
        <span className="flex items-center gap-2">
          <Clock className="h-4 w-4" />
          {formatDuration(session.duration_minutes)}
        </span>
        <span className="flex items-center gap-2">
          <Users className="h-4 w-4" />
          {session.seats_taken} / {session.capacity} booked
        </span>
      </div>

      <Card className="mt-8 p-6">
        <p className="whitespace-pre-line text-sm leading-relaxed text-content/90">
          {session.description || "No description provided."}
        </p>

        <div className="mt-6 flex items-center gap-3 border-t border-border/70 pt-5">
          <Avatar src={session.creator.avatar_url} name={session.creator.display_name} size={36} />
          <div>
            <p className="text-sm font-medium text-content">{session.creator.display_name}</p>
            <p className="text-xs text-muted">Session host</p>
          </div>
        </div>
      </Card>

      <Card className="mt-6 flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-2xl font-semibold">{formatPrice(session.price)}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted">
            <Info className="h-3.5 w-3.5" />
            Availability is confirmed when your booking is written, not when this page loaded.
          </p>
        </div>

        <div className="flex gap-2">
          {myBooking ? (
            <Button variant="destructive" onClick={() => setConfirmingCancel(true)}>
              Cancel booking
            </Button>
          ) : null}
          <Button
            onClick={onBook}
            loading={book.isPending}
            disabled={authenticated && bookDisabled}
          >
            {bookLabel}
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmingCancel}
        title="Cancel this booking?"
        description="Your seat goes straight back into the pool and someone else can take it."
        confirmLabel="Cancel booking"
        loading={cancel.isPending}
        onConfirm={onCancel}
        onCancel={() => setConfirmingCancel(false)}
      />
    </div>
  );
}
