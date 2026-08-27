"""GitHub OAuth (authorization-code flow), hand-rolled.

The frontend never sees the client secret: it only carries the ``code`` back
from GitHub and posts it here. This module exchanges that code for a GitHub
access token, reads the profile, and maps it onto a local user. The JWTs the
rest of the app uses are minted by us, not by GitHub. See DECISIONS.md D5 for
why this is ~80 lines of `requests` instead of django-allauth.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.db import IntegrityError, transaction

from .models import User

logger = logging.getLogger(__name__)

TIMEOUT = 10


class GitHubOAuthError(Exception):
    """Anything that goes wrong while talking to GitHub, with an API-facing code."""

    def __init__(self, code: str, message: str, http: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def is_configured() -> bool:
    return bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)


def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str) -> str:
    if not is_configured():
        raise GitHubOAuthError(
            "oauth_not_configured",
            "GitHub OAuth is not configured on the server.",
            http=503,
        )
    try:
        response = requests.post(
            settings.GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.OAUTH_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GitHubOAuthError("github_unreachable", "Could not reach GitHub.", http=502) from exc

    # GitHub answers 200 with an error body for a bad/expired/reused code.
    payload = response.json() if response.content else {}
    if response.status_code != 200 or "error" in payload:
        logger.warning("GitHub token exchange failed: %s", payload.get("error", response.status_code))
        raise GitHubOAuthError(
            "oauth_exchange_failed",
            payload.get("error_description") or "GitHub rejected the authorization code.",
            http=400,
        )

    token = payload.get("access_token")
    if not token:
        raise GitHubOAuthError("oauth_exchange_failed", "GitHub returned no access token.", http=400)
    return token


def fetch_profile(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        user_response = requests.get(settings.GITHUB_USER_URL, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GitHubOAuthError("github_unreachable", "Could not reach GitHub.", http=502) from exc

    if user_response.status_code != 200:
        raise GitHubOAuthError("github_profile_failed", "Could not read the GitHub profile.", http=502)

    profile = user_response.json()
    email = profile.get("email")
    if not email:
        # The user hides their email on their public profile; ask for the verified primary.
        try:
            emails_response = requests.get(settings.GITHUB_EMAILS_URL, headers=headers, timeout=TIMEOUT)
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    next((e for e in emails if e.get("verified")), None),
                )
                email = (primary or {}).get("email")
        except requests.RequestException:
            email = None  # Email is optional for us; the account is keyed on github_id.

    return {
        "github_id": str(profile["id"]),
        "login": profile.get("login") or f"gh{profile['id']}",
        "name": profile.get("name") or "",
        "avatar_url": profile.get("avatar_url") or "",
        "email": email or "",
    }


def _unique_username(preferred: str) -> str:
    """GitHub logins are unique on GitHub, but a local account may already hold one."""
    candidate = preferred[:150] or "user"
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{preferred[:140]}-{suffix}"
    return candidate


def get_or_create_user(profile: dict) -> tuple[User, bool]:
    """Return (user, is_new). Identity is the GitHub id, never the email or login."""
    user = User.objects.filter(github_id=profile["github_id"]).first()
    if user:
        # Keep the mirrored profile bits fresh, but never touch role or bio:
        # those belong to the user, not to GitHub.
        changed = []
        if profile["avatar_url"] and user.avatar_url != profile["avatar_url"]:
            user.avatar_url = profile["avatar_url"]
            changed.append("avatar_url")
        if profile["email"] and user.email != profile["email"]:
            user.email = profile["email"]
            changed.append("email")
        if changed:
            user.save(update_fields=changed)
        return user, False

    try:
        with transaction.atomic():
            user = User.objects.create(
                username=_unique_username(profile["login"]),
                email=profile["email"],
                github_id=profile["github_id"],
                display_name=profile["name"] or profile["login"],
                avatar_url=profile["avatar_url"],
                role=User.Role.USER,
                role_chosen=False,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user, True
    except IntegrityError:
        # Two callbacks for the same brand-new account raced; the loser reads the winner's row.
        existing = User.objects.filter(github_id=profile["github_id"]).first()
        if existing:
            return existing, False
        raise
