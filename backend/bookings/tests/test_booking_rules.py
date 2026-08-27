"""Single-threaded booking rules: the boring cases that must also be right."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, book_session, cancel_booking
from sessions_app.models import Session
from users.models import User


class BookingRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create(
            username="rules-creator", github_id="gh-rules-creator", role=User.Role.CREATOR
        )
        cls.alice = User.objects.create(username="alice", github_id="gh-alice")
        cls.bob = User.objects.create(username="bob", github_id="gh-bob")

    def _session(self, *, capacity=2, starts_in=timedelta(hours=2), is_active=True) -> Session:
        return Session.objects.create(
            creator=self.creator,
            title="Breathwork basics",
            description="A calm hour.",
            price="25.00",
            duration_minutes=60,
            starts_at=timezone.now() + starts_in,
            capacity=capacity,
            is_active=is_active,
        )

    def test_booking_a_started_session_is_rejected(self):
        session = self._session(starts_in=timedelta(minutes=-1))
        with self.assertRaises(BookingError) as ctx:
            book_session(user=self.alice, session_id=session.pk)
        self.assertEqual(ctx.exception.code, "already_started")
        self.assertEqual(ctx.exception.http, 409)
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_a_soft_deleted_session_is_not_found(self):
        session = self._session(is_active=False)
        with self.assertRaises(BookingError) as ctx:
            book_session(user=self.alice, session_id=session.pk)
        self.assertEqual(ctx.exception.code, "not_found")
        self.assertEqual(ctx.exception.http, 404)

    def test_sold_out_session_is_rejected(self):
        session = self._session(capacity=1)
        book_session(user=self.alice, session_id=session.pk)
        with self.assertRaises(BookingError) as ctx:
            book_session(user=self.bob, session_id=session.pk)
        self.assertEqual(ctx.exception.code, "sold_out")
        session.refresh_from_db()
        self.assertEqual(session.seats_taken, 1)

    def test_double_booking_by_the_same_user_is_rejected(self):
        session = self._session(capacity=5)
        book_session(user=self.alice, session_id=session.pk)
        with self.assertRaises(BookingError) as ctx:
            book_session(user=self.alice, session_id=session.pk)
        self.assertEqual(ctx.exception.code, "duplicate")
        session.refresh_from_db()
        self.assertEqual(session.seats_taken, 1, "the rejected attempt must not consume a seat")

    def test_cancelling_frees_the_seat_and_allows_rebooking(self):
        session = self._session(capacity=1)
        booking = book_session(user=self.alice, session_id=session.pk)

        cancel_booking(user=self.alice, booking_id=booking.pk)
        session.refresh_from_db()
        self.assertEqual(session.seats_taken, 0)

        # The freed seat is really available, to someone else...
        book_session(user=self.bob, session_id=session.pk)
        session.refresh_from_db()
        self.assertEqual(session.seats_taken, 1)

        # ...and the original booker could rebook too, because the unique index
        # only covers CONFIRMED rows.
        cancel_booking(user=self.bob, booking_id=Booking.objects.get(user=self.bob).pk)
        book_session(user=self.alice, session_id=session.pk)
        self.assertEqual(
            Booking.objects.filter(user=self.alice, session=session).count(),
            2,
            "the cancelled row is kept as history",
        )
        self.assertEqual(
            Booking.objects.filter(
                user=self.alice, session=session, status=Booking.Status.CONFIRMED
            ).count(),
            1,
        )

    def test_cancelling_twice_is_rejected(self):
        session = self._session()
        booking = book_session(user=self.alice, session_id=session.pk)
        cancel_booking(user=self.alice, booking_id=booking.pk)
        with self.assertRaises(BookingError) as ctx:
            cancel_booking(user=self.alice, booking_id=booking.pk)
        self.assertEqual(ctx.exception.code, "already_cancelled")

    def test_cancelling_someone_elses_booking_is_not_found(self):
        session = self._session()
        booking = book_session(user=self.alice, session_id=session.pk)
        with self.assertRaises(BookingError) as ctx:
            cancel_booking(user=self.bob, booking_id=booking.pk)
        # 404 rather than 403: Bob should not learn that this booking id exists.
        self.assertEqual(ctx.exception.code, "not_found")
        self.assertEqual(ctx.exception.http, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_database_rejects_an_oversell_even_without_the_service(self):
        """The backstop, tested directly.

        This is what makes the CheckConstraint worth having: it holds even for a
        write that bypasses ``book_session`` entirely.
        """
        session = self._session(capacity=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Session.objects.filter(pk=session.pk).update(seats_taken=3)

    def test_database_rejects_a_second_active_booking_row(self):
        """The other backstop: the partial unique index, tested directly."""
        session = self._session(capacity=5)
        Booking.objects.create(user=self.alice, session=session)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user=self.alice, session=session)

    def test_cancelled_rows_do_not_block_a_new_booking_row(self):
        session = self._session(capacity=5)
        Booking.objects.create(
            user=self.alice,
            session=session,
            status=Booking.Status.CANCELLED,
            cancelled_at=timezone.now(),
        )
        Booking.objects.create(
            user=self.alice,
            session=session,
            status=Booking.Status.CANCELLED,
            cancelled_at=timezone.now(),
        )
        # Two cancelled rows coexist happily; only CONFIRMED is constrained.
        Booking.objects.create(user=self.alice, session=session)
        self.assertEqual(Booking.objects.filter(user=self.alice).count(), 3)
