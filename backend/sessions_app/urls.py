from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CreatorSessionListView, SessionViewSet

router = DefaultRouter()
router.register("sessions", SessionViewSet, basename="session")

urlpatterns = [
    path("creator/sessions/", CreatorSessionListView.as_view(), name="creator-sessions"),
    path("", include(router.urls)),
]
