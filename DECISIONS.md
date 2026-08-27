# Engineering Decisions

Each entry follows the same shape: **the ambiguity → the options → what I chose → the trade-off I accepted**. These are the decisions the brief left open, not the ones it dictated.

---

## D1 — Where each booking invariant is actually enforced

**The ambiguity.** The brief requires that concurrent bookings never exceed capacity and that a user cannot hold two active bookings for one session. It does not say whether those rules live in application code, in the database, or in both — and "both" is not free, because every duplicated rule is a rule that can drift.

**The options.**

1. *Application only* — check `seats_taken` in Python before inserting. Simple, and wrong: the check and the insert are two statements, so two requests can both pass the check before either writes. Classic TOCTOU.
2. *Database only* — no counter, no lock; let a unique index and a constraint reject bad writes and translate the resulting `IntegrityError`. Correct, but every rejection arrives as an exception, and "no seats left" is a normal outcome, not an exceptional one.
3. *Serialise the writers, and keep the database as a backstop* — take a row lock on the session, do all the checking and the increment while holding it, and still declare the invariants as constraints so a future code path that forgets the lock cannot corrupt the data.

**What I chose.** Option 3. `book_session` opens a transaction, takes `SELECT ... FOR UPDATE` on the session row, and only then checks start time, duplicates and capacity before incrementing. Concurrent bookers of the same session queue at the lock, so each one sees the previous one's committed result. Locking a single row keeps contention scoped per session: a stampede on one popular session never blocks bookings on any other.

**Who owns what:**

| Invariant | In the database | In the application | Why there |
|---|---|---|---|
| bookings ≤ capacity | `CheckConstraint(seats_taken <= capacity)` | row lock + check before increment | The lock is what makes it a *friendly* 409 instead of an exception; the constraint is what makes it true even if some future code path forgets the lock |
| no duplicate active booking | partial unique index on `(user, session) WHERE status = 'CONFIRMED'` | pre-check inside the lock | The pre-check produces a clean message; only the index survives a same-user double-click that slips past it (`IntegrityError` is caught and returned as 409) |
| no booking after the session starts | — | check inside the locked transaction | Needs `now()`. A CHECK constraint cannot use a volatile function, and the risk is low because the check runs inside the same serialised section |
| only the owner mutates a session | — | queryset scoping + permission class | Authorization is application-layer by nature: the database has no concept of "the current user" here |

**Why a frontend check can never be the enforcement.** The catalogue renders `seats_remaining` — a number that was true when the response was serialised. Between that render and the click, anyone else can take the last seat. Even a check performed on the server *outside* the lock is the same bug with a shorter window. The only authoritative moment is the write itself, under the lock. That is why the UI labels availability as a hint ("Availability is confirmed when your booking is written, not when this page loaded") and treats a `sold_out` 409 on a button that looked bookable as a normal outcome, not an error state.

**The trade-off.** Two places state each rule, so they must stay in step; a migration that relaxes a constraint without touching the service would quietly widen what is possible. I accepted that because the failure mode of the alternative is silent data corruption, and because the tests pin both layers: `test_database_rejects_an_oversell_even_without_the_service` exercises the constraint directly, and deleting `select_for_update()` makes three race tests fail *on that constraint*.

---

## D2 — JWT storage: localStorage, not httpOnly cookies

**The ambiguity.** The brief says the backend issues access and refresh tokens. It says nothing about where the browser keeps them, and the two realistic answers have genuinely different threat models.

**The options.**

1. *`localStorage` + an `Authorization` header* — trivial to implement, works identically for the app, for `curl` and for the demo script, and is immune to CSRF because nothing is sent ambiently. Exposed to XSS: any script that runs on the page can read the tokens.
2. *`httpOnly` `Secure` `SameSite` cookies* — unreadable by JavaScript, so XSS cannot exfiltrate them directly. Requires CSRF tokens on every mutation, a cookie-aware refresh endpoint, and careful `SameSite` handling.

**What I chose.** Option 1, with the exposure deliberately narrowed: everything is served from one origin through nginx, there is no third-party script on any page, and the access token lives 15 minutes.

**The trade-off.** A successful XSS becomes a token theft rather than a session ride. I would move to httpOnly cookies before this saw real users, and the change is contained — `lib/api.ts` is the only file that reads or writes a token. It is listed under "what I'd improve with another day".

---

## D3 — Deleting a session is a soft delete

**The ambiguity.** "Creators can delete their own sessions" — but a session with bookings is referenced by other people's history. Hard-deleting it either cascades (destroying somebody else's records) or fails on the foreign key (a confusing 500).

**The options.** Hard delete with `CASCADE`; hard delete with `PROTECT` and an error when bookings exist; or an `is_active` flag that hides the row from the catalogue.

**What I chose.** The flag. `DELETE /api/sessions/{id}/` sets `is_active = False` and returns 204. The public catalogue filters on it, so the session disappears from the reviewer's point of view, while `/bookings/` still resolves the session for anyone who booked it. The foreign key is `PROTECT`, so nothing can quietly cascade later.

**The trade-off.** Every read path must remember to filter on `is_active`, and forgetting to is a silent bug rather than a loud one. I contained it by filtering in one place (`SessionViewSet.get_queryset`) and covering it with a test that asserts a deleted session leaves the catalogue but remains bookable-history. Booking a soft-deleted session returns 404, which is also tested.

---

## D4 — A denormalised `seats_taken` counter, not `COUNT(bookings)`

**The ambiguity.** Capacity can be checked by counting confirmed bookings at write time, or by maintaining a counter on the session.

**The options.**

1. *`COUNT` at book time* — always consistent by construction, nothing to keep in sync, but it is a second query on every booking and, more importantly, it is not something the database can enforce. There is no CHECK constraint that can express "the number of rows in another table is at most this column".
2. *A counter column* — one comparison, and it hands the database an arithmetic invariant it can hold on its own.

**What I chose.** The counter, updated with `F("seats_taken") + 1` so the arithmetic happens in the database rather than from a value read into Python, and always under the row lock.

**The trade-off.** A counter can drift from reality; a `COUNT` cannot. I paid for that with discipline and with tests: cancellation decrements under the same lock, the seed script bumps the counter for the one booking it has to write directly, and every race test asserts `seats_taken == COUNT(confirmed bookings)` rather than just asserting a number. The reason it is worth paying is D1: the counter is what makes `CheckConstraint(seats_taken <= capacity)` possible, and that constraint is the thing that catches a missing lock.

---

## D5 — Hand-rolled GitHub OAuth instead of django-allauth

**The ambiguity.** OAuth is a solved problem with a well-known Django library. The brief also wants *the backend* to issue the JWTs, which is not what an OAuth library's happy path gives you.

**The options.** `django-allauth` (+ `dj-rest-auth` to bridge to DRF and SimpleJWT); `python-social-auth`; or ~120 lines that exchange the code and read the profile directly.

**What I chose.** The 120 lines, in `users/auth_github.py`. What the app actually needs from OAuth is small and completely specified: exchange a code for a token, read `/user`, fall back to `/user/emails` when the profile email is hidden, map that onto a local account keyed by GitHub id. Wiring allauth into DRF would have meant adding two dependencies, learning their adapter/pipeline conventions, and overriding the parts that assume session login — more moving parts than the thing they replace.

**The trade-off.** No library maintenance, no free second provider: adding Google means writing a second exchange rather than adding a settings key. Since the brief asks for one provider, and since a hand-rolled exchange is testable with `requests` mocked (nine tests in `users/tests/test_oauth.py`), that seemed like the better shape. The one thing I would not hand-roll in production is token *refresh* against the provider — but this app never needs the GitHub token again after the first read.

---

## D6 — Another creator's session returns 404, not 403

**The ambiguity.** A creator PATCHing a session that belongs to somebody else could reasonably get either status. 403 says "this exists but you may not touch it"; 404 says "nothing to see here".

**The options.** Fetch the object, then compare `creator_id` and raise `PermissionDenied` (403); or scope the queryset to the caller so the lookup simply misses (404).

**What I chose.** Queryset scoping — `Session.objects.filter(creator=request.user)` for every write action. Two reasons, and the second is the one that mattered. First, 403 is an information leak: it confirms that id 42 exists and belongs to someone. Second, and more practically, the check cannot be forgotten. An object-level permission has to be remembered on every new endpoint; a scoped queryset makes the wrong rows unreachable by construction, so a future `@action` on the same viewset inherits the protection instead of needing to re-declare it.

**The trade-off.** A creator who genuinely mistypes an id of their own gets "not found", which is very slightly less helpful than "not yours". Both cases are covered in `test_authz.py`.

---

## D7 — The GitHub authorize URL is built by the backend

**The ambiguity.** The "Continue with GitHub" button needs a client id and a redirect URI. The Next.js convention is `NEXT_PUBLIC_*` environment variables — but those are inlined **at build time**, which means a reviewer's `docker compose up --build` would have to pass them as build args, and changing them would require rebuilding the image.

**The options.** Bake `NEXT_PUBLIC_GITHUB_CLIENT_ID` into the frontend build; or expose `GET /api/auth/github/authorize-url/` and have the login page ask for it at runtime.

**What I chose.** The endpoint. OAuth configuration then lives in exactly one place (the backend environment), the frontend image is configuration-free, and the endpoint can answer `{"configured": false}` — which is what lets the login page show a specific, actionable message when the reviewer has not filled in their GitHub credentials yet, rather than bouncing them to a broken GitHub page.

**The trade-off.** One extra round trip before the redirect, and a slightly unusual shape for anyone expecting the `NEXT_PUBLIC_` convention. Worth it: it is the difference between "clone, add two secrets to `.env`, run" and "clone, add two secrets, rebuild the frontend image".
