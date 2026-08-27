from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class AppUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "role_chosen", "github_id", "is_staff")
    list_filter = ("role", "role_chosen", "is_staff")
    search_fields = ("username", "email", "display_name", "github_id")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Marketplace profile",
            {"fields": ("role", "role_chosen", "github_id", "display_name", "bio", "avatar_url")},
        ),
    )
