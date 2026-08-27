"""Booking write paths.

Everything that can oversell a session lives in this module, and every check
that guards capacity happens while holding the session's row lock. The rules
this enforces, and where each one is *really* enforced, are written up in
DECISIONS.md D1.

The short version: a capacity check that runs outside the lock is a stale read.
Between "SELECT seats_taken" and "INSERT booking" another request can take the
last seat, and both requests will happily believe there was room. The lock makes
that window disappear by serialising the writers for a single session; the DB
constraints then act as a backstop for any future code path that forgets to lock.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from sessions_app.models import Session

from .models import Booking


class BookingError(Exception):
    """A rejected booking, carrying the HTTP status and machine code to return."""

    def __init__(self, code: str, message: str, http: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def book_session(*, user, session_id: int) -> Booking:
    """Book one seat, or raise BookingError. Safe to call concurrently."""
    with transaction.atomic():
        try:
            # SELECT ... FOR UPDATE. Concurrent bookers of this session queue up
            # here; everything below runs with the row held, so the checks and the
            # increment are one indivisible step.
            session = Session.objects.select_for_update().get(pk=session_id, is_active=True)
        except Session.DoesNotExist:
            raise BookingError("not_found", "Session not found.", 404) from None

        if session.starts_at <= timezone.now():
            raise BookingError("already_started", "This session has already started.", 409)

        already_booked = Booking.objects.filter(
            user=user, session=session, status=Booking.Status.CONFIRMED
        ).exists()
        if already_booked:
            raise BookingError("duplicate", "You already have an active booking for this session.", 409)

        if session.seats_taken >= session.capacity:
            raise BookingError("sold_out", "No seats remaining for this session.", 409)

        # F() so the increment is computed by the database, not from a value we
        # read into Python. Combined with the lock, seats_taken can only ever move
        # one step at a time.
        session.seats_taken = F("seats_taken") + 1
        session.save(update_fields=["seats_taken"])

        try:
            booking = Booking.objects.create(user=user, session=session)
        except IntegrityError:
            # The partial unique index fired: a genuine same-user race that got
            # past the pre-check above. Raising rolls back the whole transaction,
            # including the seat increment, and the caller sees 409 rather than 500.
            raise BookingError(
                "duplicate", "You already have an active booking for this session.", 409
            ) from None

        session.refresh_from_db(fields=["seats_taken"])
        return booking


def cancel_booking(*, user, booking_id: int) -> Booking:
    """Release a seat, or raise BookingError. Mirror image of book_session."""
    with transaction.atomic():
        # Read once, unlocked, only to learn which session row to lock.
        stub = Booking.objects.filter(pk=booking_id, user=user).values("session_id").first()
        if stub is None:
            # Also covers "someone else's booking": we do not confirm it exists.
            raise BookingError("not_found", "Booking not found.", 404)

        session = Session.objects.select_for_update().get(pk=stub["session_id"])

        # Re-read the booking now that the session is locked, so two concurrent
        # cancels cannot both decrement the counter.
        booking = Booking.objects.select_for_update().get(pk=booking_id)

        if booking.status != Booking.Status.CONFIRMED:
            raise BookingError("already_cancelled", "This booking is already cancelled.", 409)

        if session.starts_at <= timezone.now():
            raise BookingError(
                "already_started", "This session has already started and cannot be cancelled.", 409
            )

        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at"])

        # Guarded decrement: the filter keeps the counter at or above zero even if
        # the data were ever inconsistent, so we never trip the >= 0 column check.
        Session.objects.filter(pk=session.pk, seats_taken__gt=0).update(
            seats_taken=F("seats_taken") - 1
        )

        return booking
