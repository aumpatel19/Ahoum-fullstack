from django.utils import timezone
from rest_framework import serializers

from users.serializers import PublicUserSerializer

from .models import Session


class SessionSerializer(serializers.ModelSerializer):
    """Public read shape for the catalog and the detail page."""

    creator = PublicUserSerializer(read_only=True)
    seats_remaining = serializers.IntegerField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)
    has_started = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = (
            "id",
            "title",
            "description",
            "price",
            "duration_minutes",
            "starts_at",
            "capacity",
            "seats_taken",
            "seats_remaining",
            "is_sold_out",
            "has_started",
            "creator",
            "created_at",
        )
        read_only_fields = fields

    def get_has_started(self, obj: Session) -> bool:
        return obj.starts_at <= timezone.now()


class CreatorSessionSerializer(SessionSerializer):
    """Adds the numbers a creator needs on their own dashboard."""

    confirmed_bookings = serializers.IntegerField(read_only=True)

    class Meta(SessionSerializer.Meta):
        fields = SessionSerializer.Meta.fields + ("confirmed_bookings", "is_active")
        read_only_fields = fields


class SessionWriteSerializer(serializers.ModelSerializer):
    """Create/update shape. ``creator`` comes from the token, never from the body."""

    class Meta:
        model = Session
        fields = ("title", "description", "price", "duration_minutes", "starts_at", "capacity")

    def validate_starts_at(self, value):
        # Only enforced on create: an existing session may legitimately be edited
        # after it has started (e.g. fixing a typo in the description).
        if self.instance is None and value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future.")
        return value

    def validate_capacity(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Capacity must be at least 1.")
        if self.instance is not None and value < self.instance.seats_taken:
            # Otherwise the DB CheckConstraint would reject the write with a 500;
            # this turns it into a readable 400 while the constraint stays as backstop.
            raise serializers.ValidationError(
                f"Capacity cannot be lower than the {self.instance.seats_taken} "
                "seat(s) already booked."
            )
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_duration_minutes(self, value: int) -> int:
        if value < 5 or value > 24 * 60:
            raise serializers.ValidationError("Duration must be between 5 and 1440 minutes.")
        return value
