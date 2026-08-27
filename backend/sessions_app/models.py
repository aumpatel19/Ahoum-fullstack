from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Session(models.Model):
    """A bookable session published by a creator.

    ``seats_taken`` is a denormalised counter rather than a COUNT over bookings:
    it gives the booking path an O(1) capacity check and, more importantly, it
    gives the database an arithmetic invariant it can enforce on its own
    (``seats_within_capacity``). See DECISIONS.md D4.
    """

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sessions",
        on_delete=models.PROTECT,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duration_minutes = models.PositiveIntegerField(default=60)
    starts_at = models.DateTimeField(db_index=True)
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    seats_taken = models.PositiveSmallIntegerField(default=0)
    # Soft delete: bookings keep pointing at a real row, so booking history and
    # the PROTECT relation both stay intact. See DECISIONS.md D3.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            # The last line of defence: even a code path that forgets to take the
            # row lock cannot oversell a session.
            models.CheckConstraint(
                condition=Q(seats_taken__lte=F("capacity")),
                name="seats_within_capacity",
            ),
            models.CheckConstraint(condition=Q(capacity__gte=1), name="capacity_min_1"),
        ]
        indexes = [
            models.Index(fields=["is_active", "starts_at"], name="session_active_starts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.starts_at:%Y-%m-%d %H:%M}"

    @property
    def seats_remaining(self) -> int:
        return max(self.capacity - self.seats_taken, 0)

    @property
    def is_sold_out(self) -> bool:
        return self.seats_taken >= self.capacity
