from django.conf import settings
from django.db import models
from django.db.models import Q


class Booking(models.Model):
    """A user's seat on a session.

    Cancelling flips the status rather than deleting the row, so a user keeps a
    history and can rebook a session they previously cancelled. That is exactly
    why the "one active booking per user per session" rule is a *partial* unique
    index instead of ``unique_together``: it only applies to CONFIRMED rows.
    """

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="bookings", on_delete=models.CASCADE
    )
    session = models.ForeignKey(
        "sessions_app.Session", related_name="bookings", on_delete=models.PROTECT
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # DB-enforced: two simultaneous requests from the same user cannot both
            # create an active booking, whatever the application code does.
            models.UniqueConstraint(
                fields=["user", "session"],
                condition=Q(status="CONFIRMED"),
                name="uniq_active_booking_per_user_session",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="booking_user_status_idx"),
            models.Index(fields=["session", "status"], name="booking_session_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.session_id} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.CONFIRMED
