from django.urls import path

from .views import BookSessionView, CancelBookingView, MyBookingsView

urlpatterns = [
    path("sessions/<int:pk>/book/", BookSessionView.as_view(), name="session-book"),
    path("bookings/", MyBookingsView.as_view(), name="my-bookings"),
    path("bookings/<int:pk>/cancel/", CancelBookingView.as_view(), name="booking-cancel"),
]
