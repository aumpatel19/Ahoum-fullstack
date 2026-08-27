"""Idempotent demo data.

Run automatically by the container entrypoint when the database is empty, so a
reviewer's first `docker compose up` lands on a populated catalog instead of an
empty state. Safe to re-run: everything is get_or_create'd on a stable key.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, book_session
from sessions_app.models import Session
from users.models import User

CREATORS = [
    ("maya-lightwell", "Maya Lightwell", "Breathwork facilitator. Twelve years of ruining people's excuses."),
    ("arun-bodhi", "Arun Bodhi", "Sound healer and former sound engineer. Yes, both."),
]

USERS = [
    ("sam-rivers", "Sam Rivers"),
    ("nina-cole", "Nina Cole"),
    ("theo-park", "Theo Park"),
]

# (title, creator index, hours from now, capacity, price, minutes, description)
SESSIONS = [
    (
        "Sunrise Breathwork",
        0,
        18,
        12,
        "25.00",
        60,
        "A guided breathing practice to start the day with a clear head. Bring a blanket.",
    ),
    (
        "Sound Bath: Last Seat",
        1,
        30,
        1,
        "40.00",
        75,
        "Deep rest under gongs and singing bowls. One seat left - a good place to watch the "
        "booking race play out.",
    ),
    (
        "Grief Circle",
        0,
        54,
        8,
        "0.00",
        90,
        "A held space for people carrying something heavy. No fixing, no advice.",
    ),
    (
        "Somatic Movement Lab",
        1,
        78,
        16,
        "30.00",
        60,
        "Slow, curious movement for people who spend the day at a desk.",
    ),
    (
        "Evening Yoga Nidra",
        0,
        102,
        20,
        "18.00",
        45,
        "Lie down, stay awake-ish. The most restful forty-five minutes of your week.",
    ),
    (
        "Mantra & Chant Night",
        1,
        150,
        24,
        "22.00",
        90,
        "Call-and-response chanting. No singing ability required, only volume.",
    ),
    (
        "Forest Bathing Walk",
        0,
        246,
        10,
        "35.00",
        120,
        "A slow walk with long pauses. Weatherproof shoes recommended.",
    ),
    (
        "Full Moon Meditation (past)",
        1,
        -48,
        15,
        "20.00",
        60,
        "Already happened - kept in the catalogue so past bookings have somewhere to point.",
    ),
]


class Command(BaseCommand):
    help = "Create demo creators, users, sessions and bookings. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-if-empty",
            action="store_true",
            help="Do nothing if any session already exists (used by the entrypoint).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["only_if_empty"] and Session.objects.exists():
            self.stdout.write("Sessions already present, skipping seed.")
            return

        now = timezone.now()

        creators = []
        for username, display_name, bio in CREATORS:
            creator, _ = User.objects.get_or_create(
                github_id=f"seed-{username}",
                defaults={
                    "username": username,
                    "display_name": display_name,
                    "bio": bio,
                    "role": User.Role.CREATOR,
                    "role_chosen": True,
                    "email": f"{username}@example.com",
                    "avatar_url": f"https://api.dicebear.com/7.x/thumbs/svg?seed={username}",
                },
            )
            creators.append(creator)

        users = []
        for username, display_name in USERS:
            user, _ = User.objects.get_or_create(
                github_id=f"seed-{username}",
                defaults={
                    "username": username,
                    "display_name": display_name,
                    "role": User.Role.USER,
                    "role_chosen": True,
                    "email": f"{username}@example.com",
                    "avatar_url": f"https://api.dicebear.com/7.x/thumbs/svg?seed={username}",
                },
            )
            users.append(user)

        sessions = []
        for title, creator_index, hours, capacity, price, minutes, description in SESSIONS:
            session, _ = Session.objects.get_or_create(
                title=title,
                creator=creators[creator_index],
                defaults={
                    "description": description,
                    "price": Decimal(price),
                    "duration_minutes": minutes,
                    "starts_at": now + timedelta(hours=hours),
                    "capacity": capacity,
                },
            )
            sessions.append(session)

        # A handful of bookings so the dashboards are not empty. book_session is
        # used rather than raw creates so the seeded counters go through exactly
        # the same code path as a real booking.
        wanted = [
            (users[0], sessions[0]),
            (users[1], sessions[0]),
            (users[2], sessions[2]),
            (users[0], sessions[4]),
        ]
        booked = 0
        for user, session in wanted:
            try:
                book_session(user=user, session_id=session.pk)
                booked += 1
            except BookingError:
                pass  # Already booked on a previous run.

        # One past booking so the "Past" tab has something in it. book_session
        # would (correctly) refuse a session that has already started, so this one
        # is written directly - and the counter is bumped in the same breath, because
        # seats_taken must always equal the number of confirmed bookings.
        past_session = sessions[-1]
        _, created = Booking.objects.get_or_create(
            user=users[1], session=past_session, status=Booking.Status.CONFIRMED
        )
        if created:
            Session.objects.filter(pk=past_session.pk).update(seats_taken=F("seats_taken") + 1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(creators)} creators, {len(users)} users, "
                f"{len(sessions)} sessions, {booked} new bookings."
            )
        )
