# PRD — Ahoum Sessions Marketplace

Single source of truth for the assignment build. Every assignment requirement is either implemented or explicitly listed in README "Known limitations". Nothing is silently skipped.

**Rubric weighting (drives effort allocation):**

| Area | Weight |
|---|---|
| Core functionality & architecture | 40% |
| Correctness, authorization, edge cases, tests | 25% |
| Engineering decisions & debugging docs | 15% |
| AI supervision & prompt log | 10% |
| Documentation, Docker, code hygiene | 10% |

The app is 40%. 60% is correctness proof + docs + process. The booking race condition is the centerpiece; the four markdown docs are deliverables, not chores. UI polish is secondary but time-boxed, not skipped.

---

## 0. Requirement Traceability Matrix

| # | Requirement | Where implemented | Status |
|---|---|---|---|
| A1 | OAuth sign-in (Google or GitHub) | GitHub OAuth, backend code exchange | ☑ |
| A2 | Backend issues access/refresh JWTs | SimpleJWT pair from `/api/auth/oauth/github/` | ☑ |
| A3 | Roles: User and Creator | `User.role` field + `IsCreator` permission | ☑ |
| A4 | User can update basic profile | `PATCH /api/me/` | ☑ |
| A5 | Creator-only ops enforced by backend, not UI | DRF permission classes on all write endpoints | ☑ |
| B1 | Public catalog + session detail | `GET /api/sessions/`, `GET /api/sessions/{id}/` (AllowAny) | ☑ |
| B2 | Creator CRUD only own sessions | Queryset scoping to `creator=request.user` | ☑ |
| B3 | User books session; sees active/past bookings | `POST /api/sessions/{id}/book/`, `GET /api/bookings/` | ☑ |
| B4 | Creator sees own sessions + booking counts | `GET /api/creator/sessions/` with annotated counts | ☑ |
| C1 | Concurrent bookings never exceed capacity | `select_for_update` + DB CheckConstraint (§5) | ☑ |
| C2 | Same user cannot actively book same session twice | Partial unique index (status=CONFIRMED) | ☑ |
| C3 | Cannot book a session that already started | App check inside the locked transaction | ☑ |
| C4 | Automated test/script proving race gives valid final count | `test_booking_race.py` (TransactionTestCase) + `scripts/race_demo.py` | ☑ |
| C5 | DECISIONS.md: invariants in DB vs app; why frontend check insufficient | DECISIONS.md D1 | ☑ |
| D1 | Expired/invalid token gives correct API error | SimpleJWT 401 + test | ☑ |
| D2 | User cannot call Creator-only endpoints (403) | Permission + test | ☑ |
| D3 | Creator cannot edit another Creator's session (404) | Queryset scoping + test | ☑ |
| D4 | OAuth cancel/failure surfaced gracefully in UI | `/login?error=` handling + toast | ☑ |
| D5 | Automated tests for at least 2 authz/error cases | `test_authz.py` (7 cases) | ☑ |
| E1 | One-command start: `docker compose up --build` | docker-compose.yml (4 services) | ☑ |
| E2 | `.env.example` included | root `.env.example` | ☑ |
| E3 | DB data survives app-container restart; explained in README | named volume `pgdata` + README Persistence | ☑ |
| E4 | Nginx/reverse-proxy container | `nginx` service routing `/` to frontend, `/api` to backend | ☑ |
| F1 | PROMPT_LOG.md with required fields + "what AI got wrong" x2 | PROMPT_LOG.md | ☑ |
| F2 | DECISIONS.md at least 3 non-trivial decisions | DECISIONS.md (D1-D6) | ☑ |
| F3 | DEBUGGING.md at least 2 real issues | DEBUGGING.md | ☑ |
| F4 | README: setup, architecture, limitations, "with another day" | README.md | ☑ |
| F5 | Meaningful incremental commits (no dump commit) | commit plan §13 | ☑ |

---

## 1. Goals & Non-Goals

**Goal:** A compact, correct sessions marketplace: GitHub OAuth to backend-issued JWTs, role-gated CRUD, a booking endpoint that is provably safe under concurrency, four containers behind Nginx, honest engineering docs, and a clean commit trail.

**Non-goals (listed in README limitations):** payments, reviews/ratings, search beyond basic title match, email notifications, seat maps, waitlists, refresh-token rotation/blacklisting, mobile-perfect responsiveness, i18n, production hardening (HTTPS certs, secret managers).

**Guiding principle from the brief:** "A working solution with no evidence of engineering judgment will score lower than a smaller solution that is well reasoned and correctly tested." When time-pressed: cut UI scope, never cut tests or docs.

---

## 2. Locked Tech Decisions

| Layer | Choice | Why |
|---|---|---|
| Repo | Monorepo: `backend/`, `frontend/`, `nginx/`, docs at root | Reviewer clones one repo, runs one command |
| Backend | Python 3.12, Django 5, DRF | Required |
| Auth (tokens) | `djangorestframework-simplejwt` (access 15 min, refresh 7 d) | Backend issues access/refresh JWTs |
| Auth (OAuth) | GitHub OAuth, hand-rolled code exchange | Fewer moving parts than allauth; documented in DECISIONS D5 |
| DB | PostgreSQL 16, `psycopg[binary]` | Partial unique indexes + row locks are Postgres strengths |
| API docs | `drf-spectacular` at `/api/docs/` | Helps the reviewer explore |
| Backend tests | `pytest` + `pytest-django` (incl. `TransactionTestCase` for the race) | Required proof |
| Server | `gunicorn` (2 workers, sync) behind Nginx | Real WSGI serving, real parallelism for the race demo |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | Client components only; no SSR auth complexity |
| Data fetching | `@tanstack/react-query` + `axios` with JWT interceptor + refresh-on-401 | Loading/error states free; refresh in one place |
| UI | Tailwind tokens + `lucide-react` + `sonner`; hand-rolled components | Pretty without heavy dependencies |
| Infra | Docker Compose: `db`, `backend`, `frontend`, `nginx` | Required |
| Lint | `ruff` + `black` (backend), ESLint (frontend) | Hygiene |

**Deliberately NOT used:** Redis/Celery (no async work), django-allauth (heavier than one view), NextAuth (backend must issue JWTs).

---

## 3. Domain Model

### `users.User` (extends `AbstractUser`)
- `role`: choices `USER | CREATOR`, default `USER`
- `github_id`: CharField unique, indexed
- `avatar_url`, `bio`, `display_name`
- `role_chosen`: Bool, gates the one-time role selection
- Profile-updatable fields (A4): `display_name`, `bio`, `avatar_url`. Role is not self-updatable via the profile endpoint.

### `sessions_app.Session`
App named `sessions_app` because `sessions` clashes with `django.contrib.sessions`.

- `creator` FK to User, `related_name="sessions"`, PROTECT
- `title`, `description`, `price` Decimal(8,2), `duration_minutes`
- `starts_at` (indexed), `capacity`, `seats_taken` (denormalized counter)
- `is_active` (soft delete)
- Constraints: `seats_within_capacity` (`seats_taken <= capacity`), `capacity_min_1`
- Property `seats_remaining`

### `bookings.Booking`
- `user` FK, `session` FK, `status` (`CONFIRMED | CANCELLED`), `created_at`, `cancelled_at`
- Constraint: `UniqueConstraint(fields=["user","session"], condition=Q(status="CONFIRMED"))`
- Indexes on `(user, status)` and `(session, status)`

**Invariant ownership (goes into DECISIONS D1):**

| Invariant | Enforced in DB | Enforced in app | Why there |
|---|---|---|---|
| bookings <= capacity | CheckConstraint on `seats_taken` | `select_for_update` + check before increment | Lock serializes writers; constraint is the last line even if a code path forgets the lock |
| no duplicate active booking | partial unique index | pre-check for friendly 409 | Only the DB survives a same-user double-click race |
| no booking after start | — | check inside locked txn | Needs `now()`; low risk inside the serialized section |
| only owner mutates session | — | permission + queryset scoping | Authorization is application-layer by nature |

---

## 4. Architecture

```
Browser -> :8080 -> Nginx -> /api/*, /admin/*, /static-admin/* -> backend (gunicorn :8000) -> Postgres :5432 (volume pgdata)
                       \---> /*                                 -> frontend (next start :3000)
```

One public origin (`http://localhost:8080`), so no CORS in the primary path. JWTs in `localStorage`; axios interceptor attaches the access token and refreshes once on 401. Trade-off documented in DECISIONS D2.

---

## 5. The Booking Endpoint

`POST /api/sessions/{id}/book/` (IsAuthenticated; any role can book)

```python
def book_session(*, user, session_id) -> Booking:
    with transaction.atomic():
        session = Session.objects.select_for_update().get(pk=session_id, is_active=True)
        if session.starts_at <= timezone.now():   raise BookingError("already_started", ..., 409)
        if <duplicate confirmed booking exists>:  raise BookingError("duplicate", ..., 409)
        if session.seats_taken >= session.capacity: raise BookingError("sold_out", ..., 409)
        session.seats_taken = F("seats_taken") + 1
        session.save(update_fields=["seats_taken"])
        try:
            return Booking.objects.create(user=user, session=session)
        except IntegrityError:
            raise BookingError("duplicate", ..., 409)
```

`SELECT ... FOR UPDATE` serializes all bookers of one session; every check and the increment happen while holding the lock; the CheckConstraint and partial unique index reject anything that slips past app logic; `IntegrityError` surfaces as 409, never 500.

**Cancel:** `POST /api/bookings/{id}/cancel/`, owner only, same lock discipline; decrements `seats_taken` with a floor at 0.

**Error envelope:** `{"detail": "...", "code": "sold_out"}` with 401/403/404/409.

### 5.1 Race proof #1 — automated test
`backend/bookings/tests/test_booking_race.py`, extends `TransactionTestCase` (a plain `TestCase` wraps the test in one transaction, so threads would not see real concurrency and the race would be fake).

- capacity 1, 2 threads, 2 users -> exactly 1 confirmed
- capacity 5, 20 threads, 20 users -> exactly 5 confirmed
- capacity 10, same user, 8 threads -> exactly 1 confirmed (partial unique index)
- cancel-under-load keeps `seats_taken` equal to the confirmed count

### 5.2 Race proof #2 — reproducible script
`backend/scripts/race_demo.py` runs against the live compose stack over real HTTP through Nginx: creates a capacity-1 session, fires N simultaneous bookings, prints every status code, asserts exactly one 201, exits non-zero on violation.

---

## 6. Auth Design

### 6.1 GitHub OAuth (code flow, backend exchange)
1. Frontend redirects to GitHub authorize with `state` in sessionStorage.
2. GitHub redirects to `/auth/callback?code=...` (or `?error=access_denied` on cancel, which routes to `/login?error=oauth_cancelled` and toasts).
3. Frontend posts the code to `/api/auth/oauth/github/`.
4. Backend exchanges code for a GitHub token, fetches `/user` (+ `/user/emails`), gets-or-creates the User by `github_id`, returns `{access, refresh, user, is_new_user}`.
5. New users choose a role once via `/api/auth/choose-role/` (server-enforced one-time).
6. Refresh via `/api/auth/refresh/`. Logout clears tokens client-side (no blacklist; README limitation).

### 6.2 Roles & permissions
- `IsCreator` (role check), creator queryset scoped to `creator=request.user`, so another creator's session returns 404 rather than leaking existence.
- Public catalog is `AllowAny`, filtered to `is_active=True`.

### 6.3 Mandatory error cases (all automated in `test_authz.py`)
missing token 401, garbage token 401, expired token 401, USER creating a session 403, creator patching a foreign session 404, invalid refresh 401, profile role escalation ignored.

---

## 7. API Specification

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/oauth/github/` | — | `{code}` -> `{access, refresh, user, is_new_user}` |
| POST | `/api/auth/refresh/` | — | SimpleJWT refresh |
| POST | `/api/auth/choose-role/` | JWT | one-time `{role}` |
| GET/PATCH | `/api/me/` | JWT | profile; PATCH whitelist `display_name`, `bio`, `avatar_url` |
| GET | `/api/sessions/` | — | public, `?search=`, `?upcoming=`, paginated 12 |
| GET | `/api/sessions/{id}/` | — | public detail |
| POST | `/api/sessions/` | Creator | create |
| PATCH/DELETE | `/api/sessions/{id}/` | Creator+owner | capacity cannot drop below `seats_taken`; DELETE soft-deletes |
| GET | `/api/creator/sessions/` | Creator | own sessions + `confirmed_bookings` |
| POST | `/api/sessions/{id}/book/` | JWT | §5 |
| GET | `/api/bookings/` | JWT | own; `?scope=active|past` |
| POST | `/api/bookings/{id}/cancel/` | JWT+owner | only CONFIRMED and not started |
| GET | `/api/healthz/` | — | compose healthcheck |
| GET | `/api/docs/` | — | Swagger UI |

---

## 8. Backend Structure

```
backend/
  config/        settings.py (django-environ), urls.py, wsgi.py, exceptions.py
  users/         models, serializers, views (me, choose-role), permissions, auth_github, management/commands/seed.py
  sessions_app/  models, serializers, views
  bookings/      models, services.py (book/cancel), serializers, views
                 tests/ test_booking_race.py, test_authz.py, test_booking_rules.py
  scripts/race_demo.py
  Dockerfile, entrypoint.sh, requirements.txt, pyproject.toml, pytest.ini
```

### 8.1 Seed data (`manage.py seed`, idempotent)
2 creators + 3 users with fake `github_id`s, 8 sessions with varied `starts_at` (one past, one capacity-1), a few bookings. Makes the reviewer's first `docker compose up` land on a populated catalog.

---

## 9. Frontend Specification

Routes (all client components): `/login`, `/auth/callback`, `/onboarding/role`, `/` (catalog), `/sessions/[id]`, `/bookings`, `/profile`, `/creator`, `/creator/sessions/new`, `/creator/sessions/[id]/edit`.

`lib/api.ts` axios instance with interceptors; `lib/queries.ts` react-query hooks; `types/api.ts` mirrors the DRF serializers with no `any`. Every list has skeleton/empty/error states; every mutation has a spinner and a toast mapped from the error `code`. Route guards are UX only, the API enforces.

---

## 10. Design System

Dark, calm theme: background `#0B0F14`, surface `#111826`, border `#1E2A3A`, text `#E6EAF2`, muted `#8A94A6`, accent violet `#8B5CF6`. Inter via `next/font`. Cards `rounded-2xl border bg-surface`; one gradient (login hero + header strip). Hand-rolled Button, Input, Badge, Card, Tabs, ConfirmDialog, Skeleton, EmptyState, Avatar, Navbar. Micro-touches: hover lift on cards, seats pill turns amber at <=3 and red when sold out, focus-visible rings, toasts bottom-right.

---

## 11. Docker & Nginx

Four services: `db` (postgres:16-alpine, healthcheck, `pgdata` volume), `backend` (gunicorn, waits for db, migrates, seeds if empty), `frontend` (multi-stage Next standalone build), `nginx` (only published port, 8080:80).

**Persistence (E3):** Postgres writes to the named volume `pgdata`, outside the container filesystem. `docker compose restart backend` or `down`/`up` without `-v` preserves all data; only `docker compose down -v` deletes it.

---

## 12. The Four Documents

- **PROMPT_LOG.md** — entry per material AI interaction: prompt, what was used, what was changed/rejected, how it was verified. Closing section "What AI got wrong" with concrete, real examples.
- **DECISIONS.md** — at least 3 decisions in the format ambiguity -> options -> choice -> trade-off. D1 is the mandated invariant-ownership entry.
- **DEBUGGING.md** — at least 2 real issues: symptom -> diagnosis -> root cause -> fix -> verification. Captured as they happen, never invented.
- **README.md** — what it is, quick start, architecture, booking correctness with both proofs, auth flow, API table, persistence, testing, env vars, known limitations, what I would improve with another day.

---

## 13. Commit Plan (18-24 meaningful commits)

1. scaffold monorepo, gitignore, PRD, doc stubs
2. docker compose with postgres + healthcheck + pgdata volume
3. django project, settings via env, healthz
4. custom User with role and github fields
5. github oauth code exchange issuing jwt pair
6. refresh, me, one-time role choice
7. authz tests
8. session model with capacity constraints
9. public catalog + detail endpoints
10. creator CRUD with ownership scoping
11. booking model with partial unique constraint
12. book_session service with select_for_update
13. race test on TransactionTestCase
14. booking rules tests
15. cancel endpoint + creator booking counts
16. seed command + race_demo script
17. next scaffold, tailwind tokens, api client
18. login + oauth callback + role onboarding
19. catalog + session detail with booking states
20. bookings page + creator dashboard + session form
21. dockerfiles + nginx reverse proxy
22. README
23. DECISIONS, DEBUGGING, PROMPT_LOG
24. lint pass and clean-clone fixes

Never batch backend + frontend + docs in one commit.

---

## 14. Execution Phases

| Phase | Build | Verify |
|---|---|---|
| 0 | Scaffold, compose db, Django project, healthz | `/api/healthz/` returns ok |
| 1 | User model, OAuth view, JWT pair, refresh, me, role-choice | tokens issued |
| 2 | Authz tests | pytest green including expired token |
| 3 | Session model + endpoints | foreign PATCH gives 404 |
| 4 | Booking model + locked service + race test | test fails without the lock, passes with it |
| 5 | Rules tests, cancel, counts, seed, race_demo | race_demo prints 1 confirmed of N |
| 6-7 | Frontend | full user and creator journeys |
| 8 | Dockerfiles, Nginx, clean-clone up | fresh folder, one command, app on :8080 |
| 9 | Four documents | all sections filled with real content |
| 10 | Polish, lint, final matrix check | ruff/eslint clean |

---

## 15. Final Submission Checklist

- ☑ Clean clone: `cp .env.example .env` (+ GitHub creds) -> `docker compose up --build` -> app at `http://localhost:8080`
- ☑ `docker compose exec backend pytest` green (race + authz + rules)
- ☑ `race_demo.py` output pasted in README
- ☑ Restart demo done; README explains the volume
- ☑ All four docs complete; PROMPT_LOG has real "AI got wrong" entries
- ☑ Incremental commits, no dump commit
- ☑ OAuth cancel path handled
- ☑ `.env` not committed; `.env.example` is; no secrets in history
- ☑ Traceability matrix fully checked
