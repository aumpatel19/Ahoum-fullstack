import secrets

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import auth_github
from .models import User
from .serializers import (
    AuthResponseSerializer,
    ChooseRoleSerializer,
    GitHubCodeSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)


def issue_tokens(user: User) -> dict:
    """Mint our own access/refresh pair. GitHub authenticates; this API authorises."""
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class GitHubAuthorizeUrlView(APIView):
    """Where the 'Continue with GitHub' button points.

    Built server-side so the client id lives in exactly one place (the backend
    environment) instead of being baked into the frontend bundle at build time.
    """

    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        if not auth_github.is_configured():
            return Response(
                {
                    "configured": False,
                    "detail": "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and "
                    "GITHUB_CLIENT_SECRET in .env, then recreate the container with "
                    "`docker compose up -d backend` (a plain restart reuses the old "
                    "environment).",
                    "code": "oauth_not_configured",
                },
                status=status.HTTP_200_OK,
            )
        state = secrets.token_urlsafe(24)
        return Response(
            {
                "configured": True,
                "state": state,
                "authorize_url": auth_github.build_authorize_url(state),
            }
        )


class GitHubOAuthView(APIView):
    """POST {code} -> our JWT pair.

    The code is single-use and short-lived; the client secret never leaves the
    backend. A failure here is always a 4xx/5xx with a machine-readable code so
    the login page can say something useful instead of "something went wrong".
    """

    permission_classes = [AllowAny]

    @extend_schema(request=GitHubCodeSerializer, responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = GitHubCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = auth_github.exchange_code_for_token(serializer.validated_data["code"])
            profile = auth_github.fetch_profile(token)
        except auth_github.GitHubOAuthError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.http)

        user, is_new = auth_github.get_or_create_user(profile)
        if not user.is_active:
            return Response(
                {"detail": "This account has been disabled.", "code": "account_disabled"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                **issue_tokens(user),
                "is_new_user": is_new,
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    """GET the current profile, PATCH the three fields a user owns."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class ChooseRoleView(APIView):
    """One-time role selection, straight after the first OAuth login.

    Enforced server-side: once ``role_chosen`` is true the endpoint refuses,
    so a replayed request cannot turn a user into a creator later on.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChooseRoleSerializer, responses={200: UserSerializer})
    def post(self, request):
        if request.user.role_chosen:
            return Response(
                {
                    "detail": "Your role has already been set and cannot be changed.",
                    "code": "role_already_chosen",
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ChooseRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.role = serializer.validated_data["role"]
        request.user.role_chosen = True
        request.user.save(update_fields=["role", "role_chosen"])
        return Response(UserSerializer(request.user).data)
