"""Race proof #2: real HTTP, real concurrency, against the running stack.

The unit test in ``bookings/tests/test_booking_race.py`` proves the service is
safe across threads inside one process. This script proves it end to end:
requests go over the network through nginx to gunicorn's worker processes, so
the concurrency is genuinely parallel rather than thread-interleaved.

    docker compose exec backend python scripts/race_demo.py

Environment:
    RACE_DEMO_BASE_URL    default http://nginx (inside the compose network)
    RACE_DEMO_ATTEMPTS    default 10
Exit code is non-zero if the invariant is violated.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import httpx  # noqa: E402
from django.utils import timezone  # noqa: E402

from bookings.models import Booking  # noqa: E402
from sessions_app.models import Session  # noqa: E402
from users.models import User  # noqa: E402
from users.views import issue_tokens  # noqa: E402

BASE_URL = os.environ.get("RACE_DEMO_BASE_URL", "http://nginx").rstrip("/")
ATTEMPTS = int(os.environ.get("RACE_DEMO_ATTEMPTS", "10"))


def ensure_demo_accounts() -> tuple[User, list[User]]:
    creator, _ = User.objects.get_or_create(
        github_id="race-demo-creator",
        defaults={
            "username": "race-demo-creator",
            "display_name": "Race Demo Creator",
            "role": User.Role.CREATOR,
            "role_chosen": True,
        },
    )
    racers = []
    for index in range(ATTEMPTS):
        racer, _ = User.objects.get_or_create(
            github_id=f"race-demo-racer-{index}",
            defaults={
                "username": f"race-demo-racer-{index}",
                "display_name": f"Racer {index}",
                "role": User.Role.USER,
                "role_chosen": True,
            },
        )
        racers.append(racer)
    return creator, racers


async def create_session(client: httpx.AsyncClient, creator_token: str) -> dict:
    """Create the single-seat session over the API, as a creator would."""
    response = await client.post(
        "/api/sessions/",
        headers={"Authorization": f"Bearer {creator_token}"},
        json={
            "title": f"Race demo {timezone.now():%H:%M:%S}",
            "description": "One seat. Everybody grabs at once.",
            "price": "0.00",
            "duration_minutes": 30,
            "starts_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            "capacity": 1,
        },
    )
    response.raise_for_status()
    return response.json()


async def attempt_booking(client: httpx.AsyncClient, token: str, session_id: int) -> tuple[int, str]:
    response = await client.post(
        f"/api/sessions/{session_id}/book/", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        code = response.json().get("code", "created" if response.status_code == 201 else "?")
    except ValueError:
        code = "<non-json response>"
    return response.status_code, code


async def main() -> int:
    creator, racers = ensure_demo_accounts()
    creator_token = issue_tokens(creator)["access"]
    racer_tokens = [issue_tokens(racer)["access"] for racer in racers]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        health = await client.get("/api/healthz/")
        print(f"Target      : {BASE_URL}  (health: {health.json()})")

        session = await create_session(client, creator_token)
        session_id = session["id"]
        print(f"Session     : #{session_id} '{session['title']}' capacity={session['capacity']}")
        print(f"Firing      : {ATTEMPTS} simultaneous POST /api/sessions/{session_id}/book/\n")

        # asyncio.gather dispatches all of them without awaiting in between, so
        # they land on the gunicorn workers together.
        results = await asyncio.gather(
            *(attempt_booking(client, token, session_id) for token in racer_tokens)
        )

        for index, (status_code, code) in enumerate(results):
            marker = "OK   " if status_code == 201 else "     "
            print(f"  racer {index:>2}  ->  HTTP {status_code}  {code:<16} {marker}")

        final = (await client.get(f"/api/sessions/{session_id}/")).json()

    created = sum(1 for status_code, _ in results if status_code == 201)
    confirmed = Booking.objects.filter(
        session_id=session_id, status=Booking.Status.CONFIRMED
    ).count()
    seats_taken = Session.objects.get(pk=session_id).seats_taken

    print("\n" + "-" * 62)
    print(f"  HTTP 201 responses            : {created}")
    print(f"  CONFIRMED bookings in the DB  : {confirmed}")
    print(f"  session.seats_taken           : {seats_taken}")
    print(f"  capacity                      : {final['capacity']}")
    print(f"  seats_remaining (from the API): {final['seats_remaining']}")
    print("-" * 62)

    ok = created == 1 and confirmed == 1 and seats_taken == 1
    if ok:
        print(f"\nPASS: {ATTEMPTS} simultaneous attempts, exactly 1 seat sold.\n")
        return 0
    print("\nFAIL: the capacity invariant was violated.\n")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
