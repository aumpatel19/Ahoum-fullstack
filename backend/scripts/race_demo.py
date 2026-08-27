"""Race proof #2: real HTTP, real concurrency, against the running stack.

The unit tests in ``bookings/tests/test_booking_race.py`` prove the service is
safe across threads inside one process. This script proves it end to end:
requests go over the network through nginx to gunicorn's worker processes, so
the concurrency is genuinely parallel rather than thread-interleaved.

    docker compose exec backend python scripts/race_demo.py

Environment:
    RACE_DEMO_BASE_URL    default http://nginx (inside the compose network)
    RACE_DEMO_ATTEMPTS    default 10

Exit code is non-zero if the capacity invariant is violated.

Note on structure: every ORM call happens on the synchronous side of this file.
Django refuses ORM access from inside a running event loop
(SynchronousOnlyOperation), so the async part is strictly the HTTP fan-out.
"""

from __future__ import annotations

import asyncio
import logging
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

# httpx logs every request at INFO; the interesting output here is our own table.
logging.getLogger("httpx").setLevel(logging.WARNING)

BASE_URL = os.environ.get("RACE_DEMO_BASE_URL", "http://nginx").rstrip("/")
ATTEMPTS = int(os.environ.get("RACE_DEMO_ATTEMPTS", "10"))


def ensure_demo_accounts() -> tuple[str, list[str]]:
    """Create (once) the demo creator and racers, and return their access tokens."""
    creator, _ = User.objects.get_or_create(
        github_id="race-demo-creator",
        defaults={
            "username": "race-demo-creator",
            "display_name": "Race Demo Creator",
            "role": User.Role.CREATOR,
            "role_chosen": True,
        },
    )
    racer_tokens = []
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
        racer_tokens.append(issue_tokens(racer)["access"])
    return issue_tokens(creator)["access"], racer_tokens


async def attempt_booking(
    client: httpx.AsyncClient, token: str, session_id: int
) -> tuple[int, str]:
    response = await client.post(
        f"/api/sessions/{session_id}/book/", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        payload = response.json()
        code = payload.get("code", "created" if response.status_code == 201 else "?")
    except ValueError:
        code = "<non-json response>"
    return response.status_code, code


async def run_race(creator_token: str, racer_tokens: list[str], starts_at: str) -> dict:
    """Everything that touches the network. No ORM calls in here."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        health = (await client.get("/api/healthz/")).json()

        created = await client.post(
            "/api/sessions/",
            headers={"Authorization": f"Bearer {creator_token}"},
            json={
                "title": f"Race demo {starts_at[11:19]}",
                "description": "One seat. Everybody grabs at once.",
                "price": "0.00",
                "duration_minutes": 30,
                "starts_at": starts_at,
                "capacity": 1,
            },
        )
        created.raise_for_status()
        session = created.json()

        print(f"Target      : {BASE_URL}  (health: {health})")
        print(f"Session     : #{session['id']} '{session['title']}' capacity={session['capacity']}")
        print(f"Firing      : {ATTEMPTS} simultaneous POST /api/sessions/{session['id']}/book/\n")

        # gather() dispatches all of them without awaiting in between, so they
        # land on the gunicorn workers together.
        results = await asyncio.gather(
            *(attempt_booking(client, token, session["id"]) for token in racer_tokens)
        )

        final = (await client.get(f"/api/sessions/{session['id']}/")).json()

    return {"session": session, "results": list(results), "final": final}


def main() -> int:
    creator_token, racer_tokens = ensure_demo_accounts()
    starts_at = (timezone.now() + timedelta(hours=2)).isoformat()

    outcome = asyncio.run(run_race(creator_token, racer_tokens, starts_at))
    results = outcome["results"]
    session_id = outcome["session"]["id"]
    final = outcome["final"]

    for index, (status_code, code) in enumerate(results):
        marker = "  <-- got the seat" if status_code == 201 else ""
        print(f"  racer {index:>2}  ->  HTTP {status_code}  {code:<16}{marker}")

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

    if created == 1 and confirmed == 1 and seats_taken == 1:
        print(f"\nPASS: {ATTEMPTS} simultaneous attempts, exactly 1 seat sold.\n")
        return 0
    print("\nFAIL: the capacity invariant was violated.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
