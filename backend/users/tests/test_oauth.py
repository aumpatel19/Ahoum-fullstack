"""GitHub OAuth exchange, with GitHub itself mocked.

The real flow needs a browser and a GitHub app, so what is tested here is
everything on our side of the exchange: that a code turns into *our* JWT pair,
that identity is keyed on the GitHub id rather than the email or login, and
that every failure mode comes back as a typed error instead of a 500.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status

from users.models import User


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self._payload


PROFILE = {
    "id": 4242,
    "login": "octocat",
    "name": "The Octocat",
    "avatar_url": "https://avatars.example/octocat.png",
    "email": "octocat@example.com",
}


@override_settings(GITHUB_CLIENT_ID="test-client", GITHUB_CLIENT_SECRET="test-secret")
class GitHubOAuthTests(TestCase):
    def exchange(self, code="valid-code"):
        return self.client.post(
            "/api/auth/oauth/github/", {"code": code}, content_type="application/json"
        )

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_first_login_creates_a_user_and_returns_our_tokens(self, post, get):
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.return_value = FakeResponse(PROFILE)

        response = self.exchange()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertTrue(body["access"] and body["refresh"])
        self.assertTrue(body["is_new_user"])
        # A brand-new account has not picked a role yet.
        self.assertFalse(body["user"]["role_chosen"])
        self.assertEqual(body["user"]["role"], "USER")

        user = User.objects.get(github_id="4242")
        self.assertEqual(user.username, "octocat")
        self.assertEqual(user.display_name, "The Octocat")
        # The token we issued must actually authenticate against our own API.
        me = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {body['access']}")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.json()["id"], user.id)

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_login_records_last_login(self, post, get):
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.return_value = FakeResponse(PROFILE)

        self.exchange()

        user = User.objects.get(github_id="4242")
        self.assertIsNotNone(user.last_login, "signing in must stamp last_login")

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_second_login_reuses_the_account(self, post, get):
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.return_value = FakeResponse(PROFILE)

        self.exchange()
        response = self.exchange()

        self.assertFalse(response.json()["is_new_user"])
        self.assertEqual(User.objects.filter(github_id="4242").count(), 1)

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_role_survives_a_later_login(self, post, get):
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.return_value = FakeResponse(PROFILE)

        self.exchange()
        user = User.objects.get(github_id="4242")
        user.role = User.Role.CREATOR
        user.role_chosen = True
        user.save(update_fields=["role", "role_chosen"])

        response = self.exchange()

        # GitHub owns the avatar and email; it does not get to reset the role.
        self.assertEqual(response.json()["user"]["role"], "CREATOR")

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_hidden_email_falls_back_to_the_verified_primary(self, post, get):
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.side_effect = [
            FakeResponse({**PROFILE, "email": None}),
            FakeResponse(
                [
                    {"email": "secondary@example.com", "primary": False, "verified": True},
                    {"email": "primary@example.com", "primary": True, "verified": True},
                ]
            ),
        ]

        self.exchange()

        self.assertEqual(User.objects.get(github_id="4242").email, "primary@example.com")

    @patch("users.auth_github.requests.get")
    @patch("users.auth_github.requests.post")
    def test_username_collision_gets_a_suffix(self, post, get):
        User.objects.create(username="octocat", github_id="someone-else")
        post.return_value = FakeResponse({"access_token": "gh-token"})
        get.return_value = FakeResponse(PROFILE)

        self.exchange()

        self.assertEqual(User.objects.get(github_id="4242").username, "octocat-2")

    @patch("users.auth_github.requests.post")
    def test_a_bad_code_is_a_400_not_a_500(self, post):
        # GitHub answers 200 with an error body for a reused or expired code.
        post.return_value = FakeResponse(
            {"error": "bad_verification_code", "error_description": "The code is incorrect."}
        )

        response = self.exchange(code="stale")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], "oauth_exchange_failed")
        self.assertEqual(User.objects.count(), 0)

    @override_settings(GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET="")
    def test_unconfigured_server_says_so_clearly(self):
        response = self.exchange()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.json()["code"], "oauth_not_configured")

        # And the login page's URL endpoint reports it rather than 500ing.
        url_response = self.client.get("/api/auth/github/authorize-url/")
        self.assertEqual(url_response.status_code, status.HTTP_200_OK)
        self.assertFalse(url_response.json()["configured"])

    def test_authorize_url_contains_the_state_and_redirect(self):
        response = self.client.get("/api/auth/github/authorize-url/")
        body = response.json()
        self.assertTrue(body["configured"])
        self.assertIn(f"state={body['state']}", body["authorize_url"])
        self.assertIn("client_id=test-client", body["authorize_url"])
        self.assertIn("redirect_uri=", body["authorize_url"])

    def test_missing_code_is_a_validation_error(self):
        response = self.client.post("/api/auth/oauth/github/", {}, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], "validation_error")
