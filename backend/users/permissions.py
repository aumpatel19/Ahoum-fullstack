from rest_framework.permissions import BasePermission

from .models import User


class IsCreator(BasePermission):
    """Creator-only endpoints.

    This is the *only* thing that decides whether a creator action is allowed.
    The frontend hides the creator UI from plain users, but that is cosmetic:
    a hand-rolled curl with a valid USER token still lands here and gets 403.
    """

    message = "This action is only available to creator accounts."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.CREATOR)
