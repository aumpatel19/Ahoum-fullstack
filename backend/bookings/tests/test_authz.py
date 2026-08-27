"""Authorization and error-path tests for the whole API.

The point of this file is that none of these rules depend on the frontend. Every
case here is a raw HTTP request with a hand-made token, exactly what a curious
user with devtools (or curl) can send.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from bookings.models import Booking
from bookings.services import book_session
from sessions_app.models import Session
from users.models import User


def access_for(user: User) -> str:
    return str(AccessToken.for_user(user))


class AuthorizationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plain_user = User.objects.create(
            username="plain", github_id="gh-plain", role=User.Role.USER, role_chosen=True
        )
        cls.creator_a = User.objects.create(
            username="creator-a", github_id="gh-creator-a", role=User.Role.CREATOR, role_chosen=True
        )
        cls.creator_b = User.objects.create(
            username="creator-b", github_id="gh-creator-b", role=User.Role.CREATOR, role_chosen=True
        )
        cls.session_a = Session.objects.create(
            creator=cls.creator_a,
            title="Creator A's session",
            starts_at=timezone.now() + timedelta(days=1),
            capacity=10,
            duration_minutes=60,
        )

    def auth(self, user: User):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_for(user)}")

    # --- tokens -----------------------------------------------------------

    def test_protected_route_without_a_token_is_401(self):
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "not_authenticated")

    def test_protected_route_with_a_garbage_token_is_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_protected_route_with_an_expired_token_is_401(self):
        token = AccessToken.for_user(self.plain_user)
        # Backdate the token: issued and expired five minutes ago.
        token.set_exp(from_time=timezone.now() - timedelta(minutes=10), lifetime=timedelta(minutes=5))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_refresh_with_an_invalid_token_is_401(self):
        response = self.client.post("/api/auth/refresh/", {"refresh": "nonsense"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_refresh_with_a_valid_token_returns_a_new_access_token(self):
        refresh = RefreshToken.for_user(self.plain_user)
        response = self.client.post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    # --- roles ------------------------------------------------------------

    def test_plain_user_cannot_create_a_session(self):
        self.auth(self.plain_user)
        response = self.client.post(
            "/api/sessions/",
            {
                "title": "Sneaky session",
                "description": "",
                "price": "0.00",
                "duration_minutes": 60,
                "starts_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "capacity": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Session.objects.filter(title="Sneaky session").count(), 0)

    def test_plain_user_cannot_list_the_creator_dashboard(self):
        self.auth(self.plain_user)
        response = self.client.get("/api/creator/sessions/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_can_create_a_session(self):
        self.auth(self.creator_a)
        response = self.client.post(
            "/api/sessions/",
            {
                "title": "Sound bath",
                "description": "Gongs.",
                "price": "30.00",
                "duration_minutes": 45,
                "starts_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "capacity": 8,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["creator"]["id"], self.creator_a.id)

    def test_creating_a_session_in_the_past_is_rejected(self):
        self.auth(self.creator_a)
        response = self.client.post(
            "/api/sessions/",
            {
                "title": "Yesterday",
                "description": "",
                "price": "0.00",
                "duration_minutes": 60,
                "starts_at": (timezone.now() - timedelta(days=1)).isoformat(),
                "capacity": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_role_cannot_be_escalated_through_the_profile_endpoint(self):
        self.auth(self.plain_user)
        response = self.client.patch(
            "/api/me/",
            {"display_name": "Plain", "role": "CREATOR", "is_staff": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.plain_user.refresh_from_db()
        self.assertEqual(self.plain_user.role, User.Role.USER)
        self.assertFalse(self.plain_user.is_staff)
        self.assertEqual(self.plain_user.display_name, "Plain")

    def test_role_can_only_be_chosen_once(self):
        fresh = User.objects.create(username="fresh", github_id="gh-fresh")
        self.auth(fresh)

        first = self.client.post("/api/auth/choose-role/", {"role": "CREATOR"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["role"], "CREATOR")

        second = self.client.post("/api/auth/choose-role/", {"role": "USER"}, format="json")
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "role_already_chosen")
        fresh.refresh_from_db()
        self.assertEqual(fresh.role, User.Role.CREATOR)

    # --- ownership --------------------------------------------------------

    def test_creator_cannot_edit_another_creators_session(self):
        self.auth(self.creator_b)
        response = self.client.patch(
            f"/api/sessions/{self.session_a.pk}/", {"title": "Hijacked"}, format="json"
        )
        # 404, not 403: the scoped queryset never finds the row, so the API does
        # not confirm that this id exists.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.session_a.refresh_from_db()
        self.assertEqual(self.session_a.title, "Creator A's session")

    def test_creator_cannot_delete_another_creators_session(self):
        self.auth(self.creator_b)
        response = self.client.delete(f"/api/sessions/{self.session_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.session_a.refresh_from_db()
        self.assertTrue(self.session_a.is_active)

    def test_creator_can_edit_their_own_session(self):
        self.auth(self.creator_a)
        response = self.client.patch(
            f"/api/sessions/{self.session_a.pk}/", {"title": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session_a.refresh_from_db()
        self.assertEqual(self.session_a.title, "Renamed")

    def test_capacity_cannot_be_reduced_below_seats_already_booked(self):
        book_session(user=self.plain_user, session_id=self.session_a.pk)
        self.auth(self.creator_a)
        response = self.client.patch(
            f"/api/sessions/{self.session_a.pk}/", {"capacity": 0}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.session_a.refresh_from_db()
        self.assertEqual(self.session_a.capacity, 10)

    def test_deleting_a_session_is_a_soft_delete(self):
        self.auth(self.creator_a)
        response = self.client.delete(f"/api/sessions/{self.session_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.session_a.refresh_from_db()
        self.assertFalse(self.session_a.is_active)
        # Gone from the public catalog, still present for booking history.
        self.client.credentials()
        listing = self.client.get("/api/sessions/")
        self.assertEqual(listing.data["count"], 0)

    # --- booking ownership ------------------------------------------------

    def test_booking_requires_authentication(self):
        response = self.client.post(f"/api/sessions/{self.session_a.pk}/book/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_user_cannot_cancel_someone_elses_booking(self):
        booking = book_session(user=self.plain_user, session_id=self.session_a.pk)
        self.auth(self.creator_b)
        response = self.client.post(f"/api/bookings/{booking.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_bookings_list_only_shows_your_own(self):
        book_session(user=self.plain_user, session_id=self.session_a.pk)
        self.auth(self.creator_b)
        response = self.client.get("/api/bookings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    # --- public surface ---------------------------------------------------

    def test_catalog_and_detail_are_public(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/sessions/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(f"/api/sessions/{self.session_a.pk}/").status_code, status.HTTP_200_OK
        )

    def test_healthz_is_public(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
