from django.contrib import admin

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "starts_at", "capacity", "seats_taken", "is_active")
    list_filter = ("is_active", "starts_at")
    search_fields = ("title", "description", "creator__username")
