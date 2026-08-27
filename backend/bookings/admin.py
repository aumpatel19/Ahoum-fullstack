from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session", "status", "created_at", "cancelled_at")
    list_filter = ("status",)
    search_fields = ("user__username", "session__title")
