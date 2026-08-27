"""Concurrency proof for the booking path.

These tests deliberately extend ``TransactionTestCase`` rather than ``TestCase``.
``TestCase`` wraps each test in a single transaction that is rolled back at the
end; worker threads would then either not see the fixture data or block on the
test's own uncommitted rows, and the "race" would prove nothing. Real commits
are needed for `SELECT ... FOR UPDATE` in another connection to mean anything.

How to convince yourself these tests really test something: delete
``select_for_update()`` from ``bookings/services.py`` and run this file again.
``test_two_bookers_one_seat`` and ``test_twenty_bookers_five_seats`` start
failing (either an oversell, or an IntegrityError from the CheckConstraint that
catches the oversell at the database). Put it back and they pass. That is the
lock doing work, not the test agreeing with itself.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, book_session, cancel_booking
from sessions_app.models import Session
from users.models import User


class BookingRaceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.creator = User.objects.create(
            username="race-creator", github_id="gh-race-creator", role=User.Role.CREATOR
        )

    def _session(self, capacity: int) -> Session:
        return Session.objects.create(
            creator=self.creator,
            title=f"Concurrency session ({capacity} seats)",
            description="Used by the race tests.",
            price=0,
            duration_minutes=60,
            starts_at=timezone.now() + timedelta(hours=1),
            capacity=capacity,
        )

    def _users(self, count: int) -> list[User]:
        return [
            User.objects.create(username=f"racer-{i}", github_id=f"gh-racer-{i}")
            for i in range(count)
        ]

    def _book_in_thread(self, barrier: threading.Barrier, user_id: int, session_id: int) -> str:
        """One booking attempt on its own connection, released at the end.

        Every thread waits on the barrier first so the attempts overlap instead of
        politely queueing behind each other's setup work.
        """
        try:
            barrier.wait(timeout=10)
            user = User.objects.get(pk=user_id)
            book_session(user=user, session_id=session_id)
            return "confirmed"
        except BookingError as exc:
            return exc.code
        finally:
            # Threads get their own connections; leaving them open makes the
            # TransactionTestCase teardown hang while truncating tables.
            connections.close_all()

    def _run_concurrently(self, session: Session, users: list[User]) -> list[str]:
        barrier = threading.Barrier(len(users))
        with ThreadPoolExecutor(max_workers=len(users)) as pool:
            futures = [
                pool.submit(self._book_in_thread, barrier, user.pk, session.pk) for user in users
            ]
            return [future.result() for future in futures]

    def _assert_consistent(self, session: Session, expected_confirmed: int) -> None:
        session.refresh_from_db()
        confirmed = Booking.objects.filter(session=session, status=Booking.Status.CONFIRMED).count()
        self.assertEqual(confirmed, expected_confirmed, "wrong number of confirmed bookings")
        self.assertEqual(session.seats_taken, expected_confirmed, "counter drifted from reality")
        self.assertLessEqual(session.seats_taken, session.capacity, "session was oversold")

    def test_two_bookers_one_seat(self):
        """The canonical case: one seat, two simultaneous bookers, one winner."""
        session = self._session(capacity=1)
        results = self._run_concurrently(session, self._users(2))

        self.assertEqual(
            results.count("confirmed"), 1, f"expected exactly one winner, got {results}"
        )
        self.assertEqual(results.count("sold_out"), 1, f"loser should see sold_out, got {results}")
        self._assert_consistent(session, expected_confirmed=1)

    def test_twenty_bookers_five_seats(self):
        """Heavier contention: 20 threads, 5 seats, no oversell and no lost seat."""
        session = self._session(capacity=5)
        results = self._run_concurrently(session, self._users(20))

        self.assertEqual(
            results.count("confirmed"), 5, f"expected exactly 5 winners, got {results}"
        )
        self.assertEqual(results.count("sold_out"), 15)
        self._assert_consistent(session, expected_confirmed=5)

    def test_same_user_double_click(self):
        """One impatient user, eight simultaneous clicks, one booking.

        Capacity is deliberately generous: the thing under test here is the
        partial unique index, not the capacity check.
        """
        session = self._session(capacity=10)
        user = User.objects.create(username="double-clicker", github_id="gh-double")
        barrier = threading.Barrier(8)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(self._book_in_thread, barrier, user.pk, session.pk) for _ in range(8)
            ]
            results = [future.result() for future in futures]

        self.assertEqual(results.count("confirmed"), 1, f"expected one booking, got {results}")
        self.assertEqual(results.count("duplicate"), 7, f"expected seven duplicates, got {results}")
        self._assert_consistent(session, expected_confirmed=1)

    def test_cancellations_and_bookings_interleaved(self):
        """Seats freed under load are re-sellable exactly once."""
        session = self._session(capacity=3)
        holders = self._users(3)
        bookings = [book_session(user=holder, session_id=session.pk) for holder in holders]
        self._assert_consistent(session, expected_confirmed=3)

        newcomers = [
            User.objects.create(username=f"latecomer-{i}", github_id=f"gh-late-{i}")
            for i in range(3)
        ]

        barrier = threading.Barrier(6)

        def cancel_in_thread(user_id: int, booking_id: int) -> str:
            try:
                barrier.wait(timeout=10)
                cancel_booking(user=User.objects.get(pk=user_id), booking_id=booking_id)
                return "cancelled"
            except BookingError as exc:
                return exc.code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [
                pool.submit(cancel_in_thread, holders[i].pk, bookings[i].pk) for i in range(3)
            ] + [
                pool.submit(self._book_in_thread, barrier, newcomers[i].pk, session.pk)
                for i in range(3)
            ]
            results = [future.result() for future in futures]

        # The interleaving is genuinely non-deterministic: a newcomer only gets a
        # seat if it reaches the lock after a cancellation released one. What must
        # hold in every ordering is that the counter equals reality and capacity
        # is never exceeded.
        self.assertEqual(results.count("cancelled"), 3)
        confirmed = Booking.objects.filter(session=session, status=Booking.Status.CONFIRMED).count()
        session.refresh_from_db()
        self.assertEqual(session.seats_taken, confirmed)
        self.assertLessEqual(session.seats_taken, session.capacity)
