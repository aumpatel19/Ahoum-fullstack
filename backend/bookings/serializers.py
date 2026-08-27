from rest_framework import serializers

from sessions_app.serializers import SessionSerializer

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    """Bookings always travel with their session so the UI needs one request."""

    session = SessionSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ("id", "status", "created_at", "cancelled_at", "session")
        read_only_fields = fields
