from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from bookings.models import Booking
from users.permissions import IsCreator

from .models import Session
from .serializers import CreatorSessionSerializer, SessionSerializer, SessionWriteSerializer


class SessionViewSet(viewsets.ModelViewSet):
    """Public catalog reads + creator-owned writes on the same resource.

    Ownership is enforced by *scoping the queryset*, not by comparing ids after
    the fact: for a write action the queryset is already narrowed to the calling
    creator's rows, so another creator's session is simply not found (404) and
    the API never confirms that the id exists. See DECISIONS.md D6.
    """

    WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}

    # Declared so the router and the schema generator can infer the pk type;
    # get_queryset() below is what actually scopes every request.
    queryset = Session.objects.select_related("creator").all()

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            return [IsAuthenticated(), IsCreator()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action in self.WRITE_ACTIONS:
            return SessionWriteSerializer
        return SessionSerializer

    def get_queryset(self):
        base = Session.objects.select_related("creator")
        if self.action in self.WRITE_ACTIONS:
            return base.filter(creator=self.request.user)
        queryset = base.filter(is_active=True)
        if self.action != "list":
            return queryset

        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        # Upcoming-only by default; ?upcoming=false shows the full archive.
        if params.get("upcoming", "true").lower() not in ("false", "0", "no"):
            queryset = queryset.filter(starts_at__gt=timezone.now())
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "search", str, description="Case-insensitive match on title or description."
            ),
            OpenApiParameter(
                "upcoming", bool, description="Default true; false includes past sessions."
            ),
        ],
        responses={200: SessionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def create(self, request, *args, **kwargs):
        write_serializer = self.get_serializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        self.perform_create(write_serializer)
        return Response(
            SessionSerializer(write_serializer.instance).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = self.get_serializer(instance, data=request.data, partial=partial)
        write_serializer.is_valid(raise_exception=True)
        write_serializer.save()
        instance.refresh_from_db()
        return Response(SessionSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        """Soft delete: bookings must keep pointing at a real row (DECISIONS.md D3)."""
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreatorSessionListView(ListAPIView):
    """The creator dashboard: own sessions (including soft-deleted) + booking counts."""

    serializer_class = CreatorSessionSerializer
    permission_classes = [IsAuthenticated, IsCreator]

    def get_queryset(self):
        return (
            Session.objects.filter(creator=self.request.user)
            .select_related("creator")
            .annotate(
                confirmed_bookings=Count(
                    "bookings", filter=Q(bookings__status=Booking.Status.CONFIRMED), distinct=True
                )
            )
            .order_by("-starts_at")
        )
