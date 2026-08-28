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
      <div className="page grid gap-6 py-12 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-44 w-full rounded-2xl" />
        </div>
        <Skeleton className="h-56 w-full rounded-2xl" />
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
    <>
      <div className="relative overflow-hidden">
        <div className="aurora absolute inset-0" aria-hidden />
        <div className="page relative py-8 sm:py-10">
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

          <h1 className="mt-4 max-w-3xl text-3xl font-semibold leading-[1.15] sm:text-4xl">
            {session.title}
          </h1>

          <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted">
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
        </div>
      </div>

      <div className="page grid gap-6 py-8 lg:grid-cols-3 lg:items-start">
        <div className="space-y-6 lg:col-span-2">
          <Card className="p-6 sm:p-7">
            <h2 className="text-xs font-medium uppercase tracking-looser text-muted">
              About this session
            </h2>
            <p className="mt-4 whitespace-pre-line text-[15px] leading-relaxed text-content/90">
              {session.description || "No description provided."}
            </p>
          </Card>

          <Card className="flex items-center gap-4 p-6">
            <Avatar src={session.creator.avatar_url} name={session.creator.display_name} size={44} />
            <div>
              <p className="text-sm font-medium text-content">{session.creator.display_name}</p>
              <p className="mt-0.5 text-xs text-muted">Session host</p>
            </div>
          </Card>
        </div>

        {/* Sticks alongside the content on desktop so the price and the button are
            never scrolled away from. */}
        <aside className="lg:sticky lg:top-24">
          <Card className="p-6">
            <p className="text-xs font-medium uppercase tracking-looser text-muted">Price</p>
            <p className="mt-1.5 text-3xl font-semibold tabular-nums text-teal">
              {formatPrice(session.price)}
            </p>

            <div className="mt-5 flex items-center justify-between border-t hairline pt-4 text-sm">
              <span className="text-muted">Seats left</span>
              <span className="font-medium tabular-nums text-content">
                {session.seats_remaining} of {session.capacity}
              </span>
            </div>

            <div className="mt-5 space-y-2">
              {myBooking ? (
                <Button
                  variant="destructive"
                  className="w-full"
                  onClick={() => setConfirmingCancel(true)}
                >
                  Cancel booking
                </Button>
              ) : null}
              <Button
                className="w-full"
                onClick={onBook}
                loading={book.isPending}
                disabled={authenticated && bookDisabled}
              >
                {bookLabel}
              </Button>
            </div>

            <p className="mt-4 flex items-start gap-1.5 text-xs leading-relaxed text-muted">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Availability is confirmed when your booking is written, not when this page loaded.
            </p>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmingCancel}
        title="Cancel this booking?"
        description="Your seat goes straight back into the pool and someone else can take it."
        confirmLabel="Cancel booking"
        loading={cancel.isPending}
        onConfirm={onCancel}
        onCancel={() => setConfirmingCancel(false)}
      />
    </>
  );
}
