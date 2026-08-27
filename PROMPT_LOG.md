# AI Prompt Log

**Tool:** Claude Code (Claude Opus), driven from a written PRD ([PRD.md](PRD.md)) that I wrote first and referenced by section in each prompt.

**How I worked.** One phase per prompt, never "build me the app". After every generation I read the diff, ran the thing, and only then moved on. The PRD's section numbers did the heavy lifting: pointing at "§5" is shorter and less ambiguous than re-describing the booking rules each time, and it keeps the model from redesigning something I had already decided.

Times are approximate. Each entry: **what I asked → what I kept → what I changed or rejected → how I verified**.

---

### #1 · Scaffold and infrastructure skeleton
**Asked.** Set up the monorepo per PRD §2 and §8: `backend/`, `frontend/`, `nginx/`, doc stubs, `.gitignore`, `.env.example`, and a compose file with just Postgres plus a healthcheck and a named volume.
**Kept.** Nearly all of it. The compose healthcheck (`pg_isready` on an interval) and the named `pgdata` volume were right first time.
**Changed.** Added `.gitattributes` with `*.sh text eol=lf` before writing any shell script. Git on Windows would otherwise commit `entrypoint.sh` with CRLF, and the container would fail with an unhelpful `exec format`-flavoured error. This was pre-emptive, not a fix — I have lost an hour to it before.
**Verified.** `docker compose up db` reaches `healthy`; `git check-attr text eol -- backend/entrypoint.sh` reports `eol: lf`.

### #2 · Django project, settings from the environment, `/api/healthz/`
**Asked.** Django 5 + DRF project with `django-environ`, a custom user model from day one, and a health endpoint that reports database state for the compose healthcheck.
**Kept.** The settings layout and the healthz view.
**Changed.** The generated `REST_FRAMEWORK` block used `AllowAny` as the default permission. I inverted it to `IsAuthenticated` and made every public endpoint opt in explicitly. Deny-by-default means a new endpoint that forgets its permission class fails closed rather than open.
**Verified.** `manage.py check`; `/api/healthz/` returns `{"ok": true, "db": "up"}`.

### #3 · GitHub OAuth exchange and JWT issuance (PRD §6.1)
**Asked.** A hand-rolled code exchange: swap the code for a GitHub token, read the profile, fall back to `/user/emails` when the email is hidden, get-or-create by `github_id`, return our own SimpleJWT pair.
**Kept.** The overall shape, including the email fallback.
**Changed.** Three things. (a) The draft looked users up by email; I changed the key to `github_id`, because emails change and are not guaranteed to be present. (b) It let the frontend send a `role` on login, which would have been a privilege-escalation hole — replaced with the one-time, server-enforced `choose-role` endpoint. (c) I moved the authorize-URL construction into the backend (`/api/auth/github/authorize-url/`) rather than a `NEXT_PUBLIC_` variable, so OAuth config is not baked into the frontend image at build time (DECISIONS D7).
**Verified.** Nine tests in `users/tests/test_oauth.py` with `requests` mocked, including "a reused code returns 400, not 500" and "role survives a later login".

### #4 · Session and booking models (PRD §3)
**Asked.** The two models with the constraints from the spec.
**Kept.** Field layout, the soft-delete flag, both check constraints.
**Changed.** The first draft used `unique_together = ("user", "session")` for the no-duplicate-booking rule. That is wrong for this domain: it makes a cancelled booking block the same user from ever rebooking. Replaced with a partial `UniqueConstraint(condition=Q(status="CONFIRMED"))`.
**Verified.** Read the generated migration, then inspected the live database:
```
"uniq_active_booking_per_user_session" UNIQUE, btree (user_id, session_id) WHERE status = 'CONFIRMED'
"seats_within_capacity" CHECK (seats_taken <= capacity)
```
and added `test_cancelled_rows_do_not_block_a_new_booking_row` to hold the line.

### #5 · The booking service (PRD §5) — the centrepiece
**Asked.** Implement `book_session` exactly as specified: `select_for_update`, all checks inside the lock, `F()` increment, `IntegrityError` surfaced as a 409.
**Kept.** Almost verbatim; this was the part I had already designed in the PRD, which is exactly why I wrote the PRD.
**Changed.** In `cancel_booking` the draft read the booking, then locked the session, then flipped the status using the already-loaded row. Two concurrent cancels of the same booking could both pass the status check and both decrement the counter. I made it re-read the booking *after* taking the session lock, so the second one sees `CANCELLED` and returns 409.
**Verified.** `test_cancellations_and_bookings_interleaved` asserts `seats_taken == COUNT(confirmed)` after three cancels and three bookings race each other.

### #6 · Race tests (PRD §5.1)
**Asked.** Concurrency tests proving the invariant holds, on `TransactionTestCase`, with a note about why not `TestCase`.
**Kept.** The structure — barrier, thread pool, `connections.close_all()` in each thread's `finally`.
**Changed.** See "what AI got wrong" #2 below.
**Verified.** The real verification was deleting `select_for_update()` and re-running. Detail below; this is the single most useful thing I did all build.

### #7 · Seed command and the HTTP race demo
**Asked.** Idempotent demo data, and a script that fires N simultaneous bookings through nginx at gunicorn.
**Kept.** Both.
**Changed.** Two corrections, both listed below (the seed's counter drift, and the async/ORM crash).
**Verified.** `manage.py seed` run twice ("4 new bookings", then "0 new bookings"); `race_demo.py` output pasted into the README.

### #8 · Frontend: tokens, API client, design tokens
**Asked.** Axios instance with a JWT interceptor and refresh-on-401, react-query hooks, Tailwind theme tokens per PRD §10.
**Kept.** The token store and the interceptor pair.
**Changed.** The generated interceptor fired one refresh request per 401. A page that starts four queries on mount would send four refreshes and race them. I added a single shared in-flight promise. I also added an `isAuthCall` guard so a failing refresh cannot recurse into itself.
**Verified.** Minted a deliberately expired access token alongside a valid refresh token, put both in `localStorage`, loaded `/bookings` in a real browser and recorded every `/api/` response:

```
GET  /api/me/            -> 401
POST /api/auth/refresh/  -> 200
GET  /api/me/            -> 200
GET  /api/bookings/      -> 200
refresh requests : 1
redirected to login: false
```

One refresh, the original requests retried, no bounce to the login page.

### #9 · Frontend pages
**Asked.** Catalogue, detail with all booking states, bookings, profile, creator dashboard and form — with loading, empty and error states everywhere (PRD §9.3).
**Kept.** Most of the markup.
**Changed.** Rewrote the copy. The generated strings were the usual "An error occurred" / "No data found"; I keyed every message off the API's machine `code` instead, so "sold_out" says *"That was the last seat — this session just sold out."* Also added the honest line on the detail page: availability is confirmed at write time, not page load.
**Verified.** Playwright screenshots of all six pages with tokens injected into `localStorage`, asserting zero console errors on each.

### #10 · Docker, nginx, and the clean-run check
**Asked.** Four services, one published port, standalone Next build, entrypoint that waits for the database then migrates, collects static and seeds only when empty.
**Kept.** All of it.
**Changed.** Added an explicit `wait_for_db.py` even though compose already gates on the healthcheck, so the container also behaves when started on its own instead of crash-looping.
**Verified.** `docker compose up --build` from scratch; `pytest` inside the container (44 passed); restart test for volume persistence (10 sessions / 7 bookings before and after).

---

## What the AI got wrong, and how I caught it

Five real ones. Each is a thing I would have shipped if I had accepted the generated code as written.

### 1. ORM calls inside an async event loop (runtime crash)
`race_demo.py` was generated as one large `async def main()` that called `User.objects.get_or_create(...)` and `Booking.objects.filter(...).count()`. It looked fine and passed review. It died on first run with `SynchronousOnlyOperation: You cannot call this from an async context`. The fix was structural — `main()` is synchronous and owns every ORM call, `run_race()` is async and owns only HTTP. Full write-up in [DEBUGGING.md](DEBUGGING.md) #1.
**How I caught it:** by running the script against the real stack rather than trusting that it looked correct.

### 2. A race test that would have "passed" without any locking
The first version of the concurrency test extended `django.test.TestCase`. That wraps each test in a transaction which is rolled back at the end, so the worker threads — on their own connections — cannot see the fixture rows, and nothing about `SELECT ... FOR UPDATE` is exercised. It is the worst kind of test: green, and testing nothing. I switched it to `TransactionTestCase`.
**How I verified the switch mattered** — and this is the check I would want to be asked about in an interview: I deleted `select_for_update()` from `book_session` and re-ran the file.

```
FAILED bookings/tests/test_booking_race.py::BookingRaceTests::test_two_bookers_one_seat
FAILED bookings/tests/test_booking_race.py::BookingRaceTests::test_twenty_bookers_five_seats
FAILED bookings/tests/test_booking_race.py::BookingRaceTests::test_cancellations_and_bookings_interleaved
E   django.db.utils.IntegrityError: new row for relation "sessions_app_session"
    violates check constraint "seats_within_capacity"
3 failed, 1 passed in 2.78s
```

Two things fall out of that run. The tests do detect a missing lock — and the failure arrives as the *database* refusing the oversell, which is the CHECK constraint from DECISIONS D1 earning its place. (The fourth test, same-user double-click, still passed: that invariant is held by the partial unique index alone and does not need the lock.) Restoring the line: `4 passed`.

### 3. A duplicate-booking rule that would have blocked rebooking forever
The generated model used `unique_together = ("user", "session")`. Django cannot make `unique_together` conditional, so cancelling a booking would have permanently barred that user from rebooking that session — a rule nobody asked for, invisible until a user complained. Replaced with a partial `UniqueConstraint` on `status = 'CONFIRMED'`, plus a test that creates two cancelled rows and one confirmed row for the same pair.
**How I caught it:** reading the generated migration and asking "what does this do to the cancel flow?"

### 4. The seed introduced counter drift into the one invariant the project is about
The seed script needs one booking on a session that has already started, which `book_session` (correctly) refuses. The generated fallback wrote the `Booking` row directly — and did not touch `seats_taken`. Every session in the demo data would have been consistent except that one, where `seats_taken` said 0 and reality said 1. On a project whose entire premise is "the counter is trustworthy", seeding a counterexample would have been quietly embarrassing.
**How I caught it:** review, before running it. The fix bumps the counter in the same `if created:` block, with a comment saying why the direct write exists at all.

### 5. Login could set your own role
The first OAuth view accepted a `role` field from the frontend and applied it on every login, so `{"code": "...", "role": "CREATOR"}` would have made anyone a creator — and re-applied it on each sign-in. Replaced with `POST /api/auth/choose-role/`, allowed exactly once and gated on a server-side `role_chosen` flag. The profile endpoint has a hard field whitelist for the same reason.
**How I caught it:** review, then pinned with two tests — `test_role_cannot_be_escalated_through_the_profile_endpoint` and `test_role_can_only_be_chosen_once`.

---

## What I'd tell someone using AI on a task like this

The model was fastest at the parts I had already specified precisely (the booking service came out close to the PRD text) and least reliable at the parts where correctness depends on runtime context you cannot see in the diff — transaction boundaries, event loops, and "what happens the *second* time this runs". Every mistake above is in that second category, and every one was caught by running the code or by asking what a rule does to a flow other than the happy path. Reading the diff was necessary; it was not sufficient.
