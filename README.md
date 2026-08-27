# Ahoum — Sessions Marketplace

A small marketplace for live sessions: creators publish them, users book a seat, and the booking path is provably safe when a hundred people reach for the last seat at once.

Django 5 + DRF + PostgreSQL behind Next.js 14, four containers, one published port.

```
git clone <repo> && cd <repo>
cp .env.example .env        # then add your GitHub OAuth client id + secret
docker compose up --build
open http://localhost:8080
```

---

## Screenshots

| Public catalogue | Session detail (sold out) |
|---|---|
| ![Catalogue](docs/screenshots/catalog.png) | ![Session detail](docs/screenshots/session-detail-sold-out.png) |

| Creator dashboard | My bookings |
|---|---|
| ![Creator dashboard](docs/screenshots/creator-dashboard.png) | ![My bookings](docs/screenshots/bookings.png) |

---

## Quick start

**1. Configure GitHub OAuth.** Create an OAuth app at <https://github.com/settings/developers> → *New OAuth App*:

| Field | Value |
|---|---|
| Homepage URL | `http://localhost:8080` |
| Authorization callback URL | `http://localhost:8080/auth/callback` |

**2. Fill in `.env`.**

```bash
cp .env.example .env
# set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET, and change DJANGO_SECRET_KEY
```

**3. Run it.**

```bash
docker compose up --build
```

That single command builds both images, waits for Postgres to actually answer (not just to start), runs migrations, collects the admin static files, seeds demo data **only if the database is empty**, and starts gunicorn behind nginx.

| URL | What |
|---|---|
| <http://localhost:8080> | The app |
| <http://localhost:8080/api/docs/> | Swagger UI (generated from the code) |
| <http://localhost:8080/api/healthz/> | `{"ok": true, "db": "up"}` |
| <http://localhost:8080/admin/> | Django admin (`docker compose exec backend python manage.py createsuperuser`) |

The catalogue is populated on first run — 8 sessions from 2 demo creators, one of them already in the past and one with a single seat — so the app is not an empty shell on arrival. Demo accounts exist in the database but have no passwords: **sign in with your own GitHub account.** To look around as a creator, pick "I'm here to host" on the one-time role screen after your first sign-in.

**Without GitHub credentials** the app still runs, the catalogue and session pages work anonymously, and the login page tells you exactly which variables are missing instead of bouncing you to a broken GitHub page. Booking needs a signed-in account.

---

## Architecture

```
                       ┌─────────────────────────────────────────┐
  browser ── :8080 ──▶ │ nginx (the only published port)          │
                       │   /api/, /admin/, /static-admin/  ──────┼──▶ backend    Django 5 + DRF
                       │   /*                              ──────┼──▶ frontend   Next.js 14 (standalone)
                       └─────────────────────────────────────────┘         │
                                                                            ▼
                                                                    Postgres 16
                                                                    volume: pgdata
```

Everything the browser talks to is **one origin**, so there is no CORS in the primary path and no preflight on any mutation. `django-cors-headers` is configured but only matters if you hit the backend directly on `:8000` during development.

**Request flow for a booking.** The browser POSTs `/api/sessions/12/book/` with a bearer token to nginx on `:8080`. nginx proxies to gunicorn, which hands it to one of two worker processes. `BookSessionView` checks authentication, then calls `bookings.services.book_session`, which opens a transaction, takes a row lock on session 12, checks start time / duplicate / capacity, increments the counter and inserts the booking — all while holding the lock. The response is either `201` with the booking or `409` with a machine-readable code (`sold_out`, `duplicate`, `already_started`) that the frontend turns into copy.

**Backend layout.**

```
backend/
  config/         settings (env-driven), urls, the uniform error envelope
  users/          custom User, GitHub OAuth exchange, profile, one-time role choice, seed command
  sessions_app/   Session model + constraints, public catalogue, creator-scoped CRUD
  bookings/       Booking model, services.py  ← all concurrency lives here
                  tests/  race · rules · authz
  scripts/        race_demo.py, wait_for_db.py
```

`sessions_app`, not `sessions`: the latter collides with `django.contrib.sessions`.

---

## Booking correctness

This is the part of the brief worth reading the code for. The full reasoning is [DECISIONS.md D1](DECISIONS.md#d1--where-each-booking-invariant-is-actually-enforced); the summary:

- **The application serialises the writers.** `book_session` takes `SELECT ... FOR UPDATE` on the session row and performs every check *and* the increment while holding it. There is no window between "is there room?" and "take the seat".
- **The database holds the invariants regardless.** `CHECK (seats_taken <= capacity)` and a partial unique index on `(user, session) WHERE status = 'CONFIRMED'` mean even a code path that forgets the lock cannot oversell or double-book. `IntegrityError` is caught and returned as a 409, never a 500.
- **The frontend never enforces anything.** `seats_remaining` in the catalogue is a number that was true when the page rendered; between render and click, somebody else can take the seat. The UI says so, and treats a `sold_out` response on a bookable-looking button as a normal outcome.

### Proof 1 — automated tests

`backend/bookings/tests/test_booking_race.py`, on `TransactionTestCase` (a plain `TestCase` wraps the test in one transaction, so worker threads would see nothing and the race would be fake):

| Test | Setup | Asserts |
|---|---|---|
| `test_two_bookers_one_seat` | 1 seat, 2 threads | exactly 1 confirmed, loser gets `sold_out` |
| `test_twenty_bookers_five_seats` | 5 seats, 20 threads | exactly 5 confirmed, 15 `sold_out` |
| `test_same_user_double_click` | 10 seats, same user × 8 threads | exactly 1 confirmed, 7 `duplicate` |
| `test_cancellations_and_bookings_interleaved` | 3 cancels racing 3 bookings | `seats_taken == COUNT(confirmed)`, never over capacity |

Every one asserts the counter equals the actual number of confirmed bookings, not just a number.

**These tests fail without the lock.** Delete `select_for_update()` from `bookings/services.py` and re-run:

```
FAILED test_booking_race.py::BookingRaceTests::test_two_bookers_one_seat
FAILED test_booking_race.py::BookingRaceTests::test_twenty_bookers_five_seats
FAILED test_booking_race.py::BookingRaceTests::test_cancellations_and_bookings_interleaved
E   django.db.utils.IntegrityError: new row for relation "sessions_app_session"
    violates check constraint "seats_within_capacity"
3 failed, 1 passed
```

Note *how* they fail: the database refuses the oversell. Both layers are visible in one run.

### Proof 2 — real HTTP against the running stack

The unit tests prove thread safety inside one process. This fires simultaneous requests through nginx at gunicorn's separate worker processes:

```
$ docker compose exec backend python scripts/race_demo.py

Target      : http://nginx  (health: {'ok': True, 'db': 'up'})
Session     : #10 'Race demo 20:53:01' capacity=1
Firing      : 10 simultaneous POST /api/sessions/10/book/

  racer  0  ->  HTTP 201  created           <-- got the seat
  racer  1  ->  HTTP 409  sold_out
  racer  2  ->  HTTP 409  sold_out
  racer  3  ->  HTTP 409  sold_out
  racer  4  ->  HTTP 409  sold_out
  racer  5  ->  HTTP 409  sold_out
  racer  6  ->  HTTP 409  sold_out
  racer  7  ->  HTTP 409  sold_out
  racer  8  ->  HTTP 409  sold_out
  racer  9  ->  HTTP 409  sold_out

--------------------------------------------------------------
  HTTP 201 responses            : 1
  CONFIRMED bookings in the DB  : 1
  session.seats_taken           : 1
  capacity                      : 1
  seats_remaining (from the API): 0
--------------------------------------------------------------

PASS: 10 simultaneous attempts, exactly 1 seat sold.
(The demo session has been soft-deleted so it stays out of the catalogue.)
```

The script exits non-zero if the invariant is ever violated, so it works as a smoke test in CI. Turn it up with `RACE_DEMO_ATTEMPTS=50`.

---

## Auth flow

1. The login page asks the backend for the authorize URL (`GET /api/auth/github/authorize-url/`), which returns a fresh `state`. OAuth configuration therefore lives only in the backend environment — nothing is baked into the frontend bundle at build time ([D7](DECISIONS.md#d7--the-github-authorize-url-is-built-by-the-backend)).
2. The browser goes to GitHub. `state` is kept in `sessionStorage`.
3. GitHub redirects to `/auth/callback?code=…&state=…`. A mismatched or missing state is rejected. Pressing **Cancel** on GitHub's screen comes back as `?error=access_denied` and lands on `/login` with a "GitHub sign-in was cancelled" toast.
4. The frontend POSTs the code to `/api/auth/oauth/github/`. The **backend** exchanges it for a GitHub token (the client secret never leaves the server), reads the profile, gets-or-creates a user keyed on `github_id`, and returns **its own** access + refresh JWTs.
5. A brand-new account picks User or Creator once, at `/onboarding/role`. The choice is enforced server-side by a `role_chosen` flag — replaying the request later returns 409, and `PATCH /api/me/` whitelists three fields so it cannot be used to escalate.
6. Access tokens live 15 minutes. An axios interceptor refreshes once on a 401 and retries, sharing a single in-flight refresh across concurrent requests; if the refresh fails, tokens are cleared and the user lands on `/login?error=session_expired`.

Route guards in the frontend decide what to *render*. Every rule is enforced again server-side — the authorization tests are all raw HTTP with hand-made tokens.

---

## API

Full interactive docs at `/api/docs/`. Errors are always `{"detail": "...", "code": "..."}`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/auth/github/authorize-url/` | — | Where the sign-in button points; reports `configured: false` if unset |
| POST | `/api/auth/oauth/github/` | — | `{code}` → `{access, refresh, user, is_new_user}` |
| POST | `/api/auth/refresh/` | — | `{refresh}` → `{access}` |
| POST | `/api/auth/choose-role/` | JWT | One-time `{role}`; 409 afterwards |
| GET / PATCH | `/api/me/` | JWT | PATCH accepts `display_name`, `bio`, `avatar_url` only |
| GET | `/api/sessions/` | — | Public. `?search=`, `?upcoming=false`, paginated 12 |
| GET | `/api/sessions/{id}/` | — | Public detail with `seats_remaining`, `has_started`, creator |
| POST | `/api/sessions/` | Creator | 403 for a plain user |
| PATCH / DELETE | `/api/sessions/{id}/` | Creator + owner | 404 for another creator's session; DELETE is a soft delete |
| GET | `/api/creator/sessions/` | Creator | Own sessions with `confirmed_bookings` counts |
| POST | `/api/sessions/{id}/book/` | JWT | 201, or 409 `sold_out` / `duplicate` / `already_started` |
| GET | `/api/bookings/` | JWT | Own only. `?scope=active` / `?scope=past` |
| POST | `/api/bookings/{id}/cancel/` | JWT + owner | Frees the seat under the same lock; 404 for someone else's |
| GET | `/api/healthz/` | — | Compose healthcheck |

---

## Persistence

Postgres writes to the **named volume `pgdata`**, which lives in Docker's storage rather than inside a container's writable layer. Containers are disposable; the volume is not.

```bash
docker compose restart backend      # data intact
docker compose down && docker compose up   # data intact — containers recreated, volume reused
docker compose down -v              # this is the one that deletes it
```

Verified for this build:

```
before restart:  sessions: 10   bookings: 7
docker compose restart backend db
after restart:   sessions: 10   bookings: 7
```

The entrypoint seeds with `--only-if-empty`, so a restart never overwrites real data — a second run reports "Sessions already present, skipping seed."

---

## Testing

```bash
docker compose exec backend pytest          # 44 tests
docker compose exec backend pytest -v       # per-test names
docker compose exec backend python scripts/race_demo.py
```

| File | Covers |
|---|---|
| `bookings/tests/test_booking_race.py` | 4 concurrency tests (above) |
| `bookings/tests/test_booking_rules.py` | Started / soft-deleted / sold-out / duplicate bookings, cancel-and-rebook, plus both database constraints exercised directly |
| `bookings/tests/test_authz.py` | Missing, garbage and **expired** tokens; role gating; cross-creator edit and delete (404); cross-user cancel; capacity below seats booked; soft delete leaving the catalogue |
| `users/tests/test_oauth.py` | The OAuth exchange with GitHub mocked: new vs returning user, hidden email fallback, username collisions, reused code → 400 not 500, unconfigured server |

**The OAuth unhappy paths** are covered by driving the callback route with exactly the query strings GitHub sends. Verified in a browser against the running stack:

| What GitHub sends back | Where you end up | What you're told |
|---|---|---|
| `?error=access_denied` (you pressed Cancel) | `/login` | "GitHub sign-in was cancelled." |
| `?code=…&state=<wrong>` | `/login` | "The sign-in request didn't match. Please start again." |
| no `code` at all | `/login` | "GitHub couldn't complete the sign-in. Please try again." |

No blank screens and no unhandled errors in any of the three. The happy path needs real GitHub credentials in `.env`; the server side of it is covered by `users/tests/test_oauth.py` with GitHub mocked.

Running them locally instead of in Docker needs a Postgres to point at:

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
DATABASE_URL=postgres://app:change-me@localhost:5432/marketplace .venv/Scripts/pytest
```

---

## Environment variables

| Variable | Default in `.env.example` | Notes |
|---|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `marketplace` / `app` / `change-me` | Consumed by the `db` service |
| `DATABASE_URL` | `postgres://app:change-me@db:5432/marketplace` | Must match the three above |
| `DJANGO_SECRET_KEY` | `change-me…` | **Change it.** |
| `DJANGO_DEBUG` | `1` | Set `0` for anything real |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend,nginx` | Comma-separated |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8080` | Only matters when bypassing nginx |
| `ACCESS_TOKEN_LIFETIME_MIN` | `15` | |
| `REFRESH_TOKEN_LIFETIME_DAYS` | `7` | |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | *(empty)* | From your GitHub OAuth app |
| `OAUTH_REDIRECT_URI` | `http://localhost:8080/auth/callback` | Must match the app exactly |
| `NEXT_PUBLIC_API_BASE` | `/api` | Relative, so the bundle carries no hostname |

`.env` is gitignored; `.env.example` is committed and contains no secrets.

---

## Known limitations

Deliberate omissions, not oversights:

- **Role is chosen once and cannot be changed.** Simplifies the authorization story; a real product needs an account-settings path with a re-verification step.
- **No refresh-token blacklist.** Signing out clears tokens client-side. A stolen refresh token stays valid for its 7 days. `rest_framework_simplejwt.token_blacklist` is a settings change plus a migration.
- **Tokens in `localStorage`,** with the XSS trade-off accepted and explained in [D2](DECISIONS.md#d2--jwt-storage-localstorage-not-httponly-cookies).
- **No payments.** `price` is displayed and stored; nothing charges anyone.
- **Search is a case-insensitive `LIKE`** on title and description. No ranking, facets or full-text index.
- **No waitlist.** Sold out is sold out; a freed seat goes to whoever asks first.
- **No email or notifications.**
- **No rate limiting.** The booking endpoint would want it before facing the public.
- **Responsive, not mobile-perfected.** Layouts collapse sensibly; they have not been tuned below ~380px.
- **No HTTPS.** nginx serves plain HTTP for local review; production needs certificates and `Secure` cookies.
- **Timezones are the browser's.** Times are stored in UTC and rendered in local time, with no per-session timezone field.

---

## What I'd do with another day

1. **A waitlist**, using `SELECT ... FOR UPDATE SKIP LOCKED` to hand a freed seat to the longest-waiting person without two workers grabbing the same one. It reuses the locking discipline that is already here.
2. **Move JWTs to httpOnly cookies** with CSRF tokens and refresh rotation with reuse detection. Contained: `lib/api.ts` is the only file that touches a token today.
3. **Playwright E2E in CI** — the booking race as a browser test: two contexts, one seat, one winner. The screenshot harness used for this README is most of the way there already.
4. **A GitHub Actions pipeline**: ruff + black --check, eslint + tsc, pytest against a Postgres service, a compose smoke test that boots the stack and runs `race_demo.py`, gating merges on the invariant.
5. **Observability** — structured JSON logs with a request id, and a counter for `sold_out` vs `confirmed` bookings, which is exactly the signal that tells you a session needed a bigger room.
6. **Rate limiting** on `/book/` and the OAuth exchange (DRF throttling, or nginx `limit_req` for the cheap version).
7. **Load-test the lock.** The current proof shows correctness under contention, not throughput. I would want to know where `SELECT ... FOR UPDATE` on one hot row starts queueing, and at what point the waitlist design above becomes necessary rather than nice.

---

## Documentation

| Document | What's in it |
|---|---|
| [DECISIONS.md](DECISIONS.md) | Seven decisions the brief left open — invariant ownership, token storage, soft delete, the denormalised counter, hand-rolled OAuth, 404-vs-403, runtime OAuth config |
| [DEBUGGING.md](DEBUGGING.md) | Four real issues, including one where my first diagnosis was wrong and one reported from use |
| [PROMPT_LOG.md](PROMPT_LOG.md) | How the AI tooling was used, and five things it got wrong that I caught |
| [PRD.md](PRD.md) | The spec I wrote before starting, and worked from |
