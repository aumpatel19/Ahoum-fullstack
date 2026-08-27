from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user.

    Accounts are created by the GitHub OAuth exchange rather than by password
    signup, so ``github_id`` is the real identity key. It stays nullable so that
    locally created accounts (``createsuperuser``) remain possible; Postgres
    treats NULLs as distinct, so the unique index still holds.
    """

    class Role(models.TextChoices):
        USER = "USER", "User"
        CREATOR = "CREATOR", "Creator"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.USER)
    # Role is picked once, right after the first OAuth login. Storing the fact
    # separately from the value lets the server reject any later change without
    # having to guess whether "USER" was chosen or merely defaulted.
    role_chosen = models.BooleanField(default=False)

    github_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)

    class Meta:
        db_table = "users_user"

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"

    @property
    def is_creator(self) -> bool:
        return self.role == self.Role.CREATOR

    @property
    def public_name(self) -> str:
        return self.display_name or self.username
