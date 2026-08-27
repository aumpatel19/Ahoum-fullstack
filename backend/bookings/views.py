from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import BookingSerializer
from .services import BookingError, book_session, cancel_booking


def _error(exc: BookingError) -> Response:
    """Every booking rejection uses the same envelope as the rest of the API."""
    return Response({"detail": exc.message, "code": exc.code}, status=exc.http)


class BookSessionView(APIView):
    """POST /api/sessions/{id}/book/

    Any authenticated account can book, creators included. All of the
    interesting work (and all of the concurrency safety) is in
    ``bookings.services.book_session``.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={201: BookingSerializer},
        description=(
            "Books one seat. Returns 409 with code sold_out, duplicate or "
            "already_started when the booking cannot be honoured."
        ),
    )
    def post(self, request, pk: int):
        try:
            booking = book_session(user=request.user, session_id=pk)
        except BookingError as exc:
            return _error(exc)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class CancelBookingView(APIView):
    """POST /api/bookings/{id}/cancel/ - owner only, releases the seat."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: BookingSerializer})
    def post(self, request, pk: int):
        try:
            booking = cancel_booking(user=request.user, booking_id=pk)
        except BookingError as exc:
            return _error(exc)
        booking.refresh_from_db()
        return Response(BookingSerializer(booking).data)


class MyBookingsView(ListAPIView):
    """GET /api/bookings/?scope=active|past - always scoped to the caller."""

    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "scope",
                str,
                description=(
                    "active = confirmed and not yet started (default all); "
                    "past = cancelled or finished."
                ),
            )
        ],
        responses={200: BookingSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Booking.objects.filter(user=self.request.user).select_related(
            "session", "session__creator"
        )
        scope = self.request.query_params.get("scope")
        now = timezone.now()
        if scope == "active":
            return queryset.filter(status=Booking.Status.CONFIRMED, session__starts_at__gt=now)
        if scope == "past":
            return queryset.filter(
                Q(status=Booking.Status.CANCELLED) | Q(session__starts_at__lte=now)
            )
        return queryset
