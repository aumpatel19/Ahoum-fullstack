from django.contrib import admin
from django.db import connection
from django.urls import include, path
from drf_spectacular.utils import OpenApiExample, extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    responses={
        200: {"type": "object", "properties": {"ok": {"type": "boolean"}, "db": {"type": "string"}}}
    },
    examples=[OpenApiExample("healthy", value={"ok": True, "db": "up"})],
    description="Liveness and database readiness probe used by the compose healthcheck.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request):
    """Liveness + DB readiness, used by the compose healthcheck."""
    db_state = "up"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - report degraded rather than raising
        db_state = "down"
    return Response({"ok": db_state == "up", "db": db_state})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/healthz/", healthz, name="healthz"),
    path("api/", include("users.urls")),
    path("api/", include("sessions_app.urls")),
    path("api/", include("bookings.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
