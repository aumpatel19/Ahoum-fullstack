from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ChooseRoleView, GitHubAuthorizeUrlView, GitHubOAuthView, MeView

urlpatterns = [
    path(
        "auth/github/authorize-url/", GitHubAuthorizeUrlView.as_view(), name="github-authorize-url"
    ),
    path("auth/oauth/github/", GitHubOAuthView.as_view(), name="github-oauth"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/choose-role/", ChooseRoleView.as_view(), name="choose-role"),
    path("me/", MeView.as_view(), name="me"),
]
