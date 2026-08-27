"""The two "see your own stuff" requirements, over HTTP.

The brief asks that a user can see active *and past* bookings, and that a
creator can see their sessions with booking counts. Both are read paths that are
easy to get subtly wrong - a cancelled booking that still shows as active, or a
count that includes cancellations - and neither is covered by the concurrency or
authorization suites.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from bookings.models import Booking
from bookings.services import book_session, cancel_booking
from sessions_app.models import Session
from users.models import User


class BookingListingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create(
            username="list-creator", github_id="gh-list-creator", role=User.Role.CREATOR
        )
        cls.other_creator = User.objects.create(
            username="list-other", github_id="gh-list-other", role=User.Role.CREATOR
        )
        cls.user = User.objects.create(username="list-user", github_id="gh-list-user")

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def make_session(self, title, *, creator=None, hours=5, capacity=10) -> Session:
        return Session.objects.create(
            creator=creator or self.creator,
            title=title,
            starts_at=timezone.now() + timedelta(hours=hours),
            capacity=capacity,
            duration_minutes=60,
        )

    def titles(self, response) -> set[str]:
        return {row["session"]["title"] for row in response.data["results"]}

    # --- active vs past ---------------------------------------------------

    def test_upcoming_confirmed_booking_is_active(self):
        session = self.make_session("Upcoming")
        book_session(user=self.user, session_id=session.pk)
        self.auth(self.user)

        active = self.client.get("/api/bookings/?scope=active")
        past = self.client.get("/api/bookings/?scope=past")

        self.assertEqual(active.status_code, status.HTTP_200_OK)
        self.assertEqual(self.titles(active), {"Upcoming"})
        self.assertEqual(past.data["count"], 0)

    def test_cancelling_moves_a_booking_from_active_to_past(self):
        session = self.make_session("Changed my mind")
        booking = book_session(user=self.user, session_id=session.pk)
        self.auth(self.user)
        self.assertEqual(
            self.titles(self.client.get("/api/bookings/?scope=active")), {"Changed my mind"}
        )

        cancel_booking(user=self.user, booking_id=booking.pk)

        self.assertEqual(self.client.get("/api/bookings/?scope=active").data["count"], 0)
        self.assertEqual(
            self.titles(self.client.get("/api/bookings/?scope=past")), {"Changed my mind"}
        )

    def test_a_session_that_has_started_moves_to_past(self):
        session = self.make_session("Already happened")
        book_session(user=self.user, session_id=session.pk)
        # Booking a started session is refused, so the session is moved backwards
        # after the fact - which is what actually happens as time passes.
        Session.objects.filter(pk=session.pk).update(starts_at=timezone.now() - timedelta(hours=1))
        self.auth(self.user)

        self.assertEqual(self.client.get("/api/bookings/?scope=active").data["count"], 0)
        self.assertEqual(
            self.titles(self.client.get("/api/bookings/?scope=past")), {"Already happened"}
        )

    def test_no_scope_returns_everything(self):
        upcoming = self.make_session("Still to come")
        finished = self.make_session("Done")
        book_session(user=self.user, session_id=upcoming.pk)
        book_session(user=self.user, session_id=finished.pk)
        Session.objects.filter(pk=finished.pk).update(starts_at=timezone.now() - timedelta(hours=2))
        self.auth(self.user)

        self.assertEqual(self.client.get("/api/bookings/").data["count"], 2)

    # --- creator dashboard counts ----------------------------------------

    def test_creator_sees_own_sessions_with_confirmed_counts(self):
        mine = self.make_session("Mine", capacity=5)
        self.make_session("Theirs", creator=self.other_creator)

        first = User.objects.create(username="b1", github_id="gh-b1")
        second = User.objects.create(username="b2", github_id="gh-b2")
        book_session(user=first, session_id=mine.pk)
        book_session(user=second, session_id=mine.pk)

        self.auth(self.creator)
        response = self.client.get("/api/creator/sessions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = {row["title"]: row for row in response.data["results"]}
        self.assertEqual(set(rows), {"Mine"}, "a creator must not see another creator's sessions")
        self.assertEqual(rows["Mine"]["confirmed_bookings"], 2)
        self.assertEqual(rows["Mine"]["seats_taken"], 2)

    def test_cancelled_bookings_are_not_counted(self):
        session = self.make_session("Half empty", capacity=5)
        stayer = User.objects.create(username="stayer", github_id="gh-stayer")
        leaver = User.objects.create(username="leaver", github_id="gh-leaver")
        book_session(user=stayer, session_id=session.pk)
        leaving = book_session(user=leaver, session_id=session.pk)
        cancel_booking(user=leaver, booking_id=leaving.pk)

        self.auth(self.creator)
        row = self.client.get("/api/creator/sessions/").data["results"][0]

        self.assertEqual(row["confirmed_bookings"], 1, "a cancelled booking must not be counted")
        self.assertEqual(row["seats_taken"], 1, "the counter must agree with the count")
        self.assertEqual(Booking.objects.filter(session=session).count(), 2, "history is kept")

    def test_creator_dashboard_includes_soft_deleted_sessions(self):
        session = self.make_session("Removed later")
        self.auth(self.creator)
        self.client.delete(f"/api/sessions/{session.pk}/")

        rows = self.client.get("/api/creator/sessions/").data["results"]
        removed = next(row for row in rows if row["title"] == "Removed later")
        # Gone from the public catalogue, still visible to its owner.
        self.assertFalse(removed["is_active"])
        self.client.credentials()
        self.assertEqual(self.client.get("/api/sessions/").data["count"], 0)
