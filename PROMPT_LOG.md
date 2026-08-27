# AI Prompt Log

**Tool used:** Claude Code, running Claude Opus. That was the only AI tool I used.

## How I actually worked

I want to be straight about this, because it changes how you should read the rest of the file.

I did not type most of this code. I wrote the spec first — [PRD.md](PRD.md) — and that is where my real work went: the stack choices, the data model, the booking design (row lock plus database constraints), which invariant lives where, and the commit plan. Then I handed that spec to Claude Code a section at a time and let it write the code.

So my job on this project was closer to spec, review and test than to typing. I checked the output by running it — tests, the compose stack, the app in a browser — rather than by reading every line as it appeared. Some things I caught that way. Some things I missed, and one of them I only found by using the app myself. Both kinds are below.

The spec mattered more than any individual prompt. Pointing at "§5" was shorter than re-explaining the booking rules every time, and it stopped the model redesigning things I had already decided. Several of the traps I was worried about never happened, because the spec had already ruled them out.

Each entry: **what I asked for → what came back → what changed → how I checked it.**

---

### 1. Scaffold, Docker and the Django project
*Claude Code / Opus*

**Asked for.** The repo layout from PRD §2 and §8: `backend/`, `frontend/`, `nginx/`, doc stubs, `.env.example`, and a compose file with Postgres, a healthcheck and a named volume. Then the Django project with settings read from the environment and a `/api/healthz/` endpoint.

**Came back.** Close to what I wanted.

**Changed.** Two things. A `.gitattributes` with `*.sh text eol=lf` went in before any shell script existed — I am on Windows, and a CRLF `entrypoint.sh` fails inside a Linux container with a message that tells you nothing useful. And the DRF defaults came back with `AllowAny`; I switched the default to `IsAuthenticated` so public endpoints have to opt in. A forgotten permission class should fail closed, not open.

**Checked.** `docker compose up db` went healthy, `/api/healthz/` returned `{"ok": true, "db": "up"}`.

---

### 2. GitHub OAuth and JWTs
*Claude Code / Opus*

**Asked for.** The hand-rolled exchange from PRD §6.1: swap the code for a GitHub token, read the profile, fall back to `/user/emails` when the email is private, find-or-create the user by GitHub id, return our own JWT pair.

**Came back.** Working, including the email fallback.

**Changed.** One thing I added on top of the spec: the authorize URL is built by the backend and served from `/api/auth/github/authorize-url/`, instead of putting the client id in a `NEXT_PUBLIC_` variable. Next.js bakes those in at build time, so the reviewer would have had to rebuild the frontend image after editing `.env`. This way the OAuth config lives in one place and a backend restart is enough. That became DECISIONS D7.

**Checked.** Nine tests with `requests` mocked, including a reused code returning 400 instead of 500. Later, with my own OAuth app configured, GitHub's page came up saying "Sign in to GitHub to continue to Ahoum", which confirmed the client id and redirect URI were right.

---

### 3. Models and the booking service
*Claude Code / Opus*

**Asked for.** The models and constraints from PRD §3, then `book_session` exactly as written in §5.

**Came back.** Very close to the spec. This was the smoothest part of the build, and I think that is the point: I had already made the hard decisions, so there was little room to get it wrong.

**Changed.** One real fix, in `cancel_booking`. The draft read the booking, then locked the session, then flipped the status using the row it had already loaded. Two people cancelling the same booking at once could both pass the status check and both give back a seat. It now re-reads the booking *after* taking the lock, so the second one sees `CANCELLED` and gets a 409.

**Checked.** `test_cancellations_and_bookings_interleaved` runs three cancels against three bookings and asserts `seats_taken` still equals the number of confirmed bookings.

---

### 4. The race tests
*Claude Code / Opus*

**Asked for.** The four concurrency tests from PRD §5.1, on `TransactionTestCase`.

**Note on that.** My spec called for `TransactionTestCase` and said why: a normal `TestCase` wraps the test in one transaction that gets rolled back, so worker threads on their own connections see nothing, and the test passes while proving nothing. I flagged it up front because it is the obvious default and it is wrong here. It never came up as a mistake, because the spec had already closed it off.

**Changed.** I found a bug in the generated test before running it. The interleaved test called a helper that creates users named `racer-0`, `racer-1`, `racer-2` — and called it twice in the same test. The second call would have blown up on the unique username. Small, but it would have looked like a real failure and cost time to chase.

**Checked.** This is the check I care most about. I deleted `select_for_update()` from the service and ran the file again:

```
FAILED test_two_bookers_one_seat
FAILED test_twenty_bookers_five_seats
FAILED test_cancellations_and_bookings_interleaved
E   django.db.utils.IntegrityError: new row for relation "sessions_app_session"
    violates check constraint "seats_within_capacity"
3 failed, 1 passed
```

Three of four fail without the lock, and they fail because the *database* refuses the oversell. That tells me the tests are real and that both layers do something. Put the lock back: 4 passed. (The fourth test, one user double-clicking, still passes without the lock — that rule is held by the partial unique index on its own.)

---

### 5. Seed data and the HTTP race demo
*Claude Code / Opus*

**Asked for.** Idempotent demo data, and a script that fires ten bookings at once through nginx so the race runs across gunicorn worker processes, not just threads.

**Changed.** The seed had a real bug. It needs one booking on a session that already started, which `book_session` correctly refuses, so it wrote the `Booking` row directly — and did not touch `seats_taken`. Every seeded session would have been consistent except that one. On a project whose whole point is "the counter can be trusted", shipping a counterexample in the demo data would have been bad. It now bumps the counter in the same block.

**Checked.** Ran the seed twice: "4 new bookings", then "0 new bookings". The demo script prints one 201 and nine 409s and exits non-zero if the numbers are ever wrong.

---

### 6. Frontend
*Claude Code / Opus*

**Asked for.** The routes from PRD §9 with the theme tokens from §10, and loading, empty and error states everywhere.

**Changed.** Two things worth mentioning. The refresh interceptor fired one refresh request per 401, so a page starting four queries would send four refreshes and race them; it now shares one in-flight promise. And I had all the error copy rewritten to key off the API's error codes instead of generic "An error occurred" strings, so a sold-out booking says "That was the last seat — this session just sold out."

**Checked.** Put a deliberately expired access token in `localStorage` and loaded `/bookings` in a browser:

```
GET  /api/me/            -> 401
POST /api/auth/refresh/  -> 200
GET  /api/me/            -> 200
GET  /api/bookings/      -> 200
refresh requests : 1
```

One refresh, the original requests retried, no bounce to the login page.

---

### 7. Docker, nginx and a clean-clone run
*Claude Code / Opus*

**Asked for.** Four services, one published port, a standalone Next build, and an entrypoint that waits for the database, migrates, collects static and seeds only if the database is empty.

**Checked.** Cloned the repo into a fresh folder, copied `.env.example` to `.env`, ran `docker compose up --build`, and it came up. Ran the tests inside the container. Ran the race demo. Then checked persistence: 10 sessions and 7 bookings before a restart, the same after.

---

### 8. Checking the finished thing against the brief
*Claude Code / Opus*

**Asked for.** A line-by-line audit of the repo against the actual assignment text.

**Found.** Two requirements had no test behind them — "see active/past bookings" and "creator sees booking counts". The features worked, but nothing would have caught a cancelled booking still showing as active, or a count that included cancellations. Added seven tests for exactly those. That took the suite from 44 to 51.

---

## What the AI got wrong, and what it cost

### 1. Database calls inside an async event loop
The race demo script was written as one big `async def main()` that also did the ORM work — creating demo users, counting bookings at the end. It looked fine. It died on the first run:

```
django.core.exceptions.SynchronousOnlyOperation:
    You cannot call this from an async context - use a thread or sync_to_async.
```

Reading it would not have caught this. Running it did, immediately. The fix was structural: the synchronous function owns all the database work, and the async part is only the HTTP fan-out. Written up in [DEBUGGING.md](DEBUGGING.md) #1.

### 2. The mobile navigation was broken and I shipped it
This is the one that actually got past everything. Every nav link was hidden below the 640px breakpoint, with nothing put in its place — the standard "hide on mobile" pattern with the other half missing. On a phone the header had the logo and nothing else. A creator could not reach their own dashboard at all. On top of that, `/login` was using the navbar's Browse link as its back button, so when that link disappeared the page became a dead end.

I found it by opening the app and trying to use it. Not by review, and not by any test.

The reason it got through is worth writing down: screenshots had been taken of every page during the build, but only at 1280px wide. The automated check that was supposed to catch UI problems was blind to the whole category of problem I hit. Full write-up in [DEBUGGING.md](DEBUGGING.md) #4.

### 3. It told me to restart the backend, and that does not work
When I added my GitHub credentials to `.env`, the instruction — in the README, in the login page's warning, and in the API's own error message — said to restart the backend. I did. Nothing changed; the app still said OAuth was not configured.

`docker compose restart` reuses the container's existing environment. It does not re-read `.env`. You need `docker compose up -d backend` to recreate the container. Wrong instruction in three places, and it would have hit whoever reviews this too. All three are fixed now.

### 4. A first diagnosis that was confidently wrong
An early smoke test failed with `Content-Type header is "text/html", not "application/json"`. The first explanation offered was DRF's browsable API renderer, and the renderer config was changed to match. Same error. The actual cause was a `DisallowedHost` 400 — Django's test client sends `Host: testserver` and I was calling it outside the test runner, so `ALLOWED_HOSTS` never got patched. The HTML was an error page, and DRF was never involved.

What I take from it: the error message pointed at the wrong layer, and one round of guessing made it worse. Printing the status code and the body found it in one step. [DEBUGGING.md](DEBUGGING.md) #2.

### 5. A test assertion that could not fail
One of the browser checks tested the Past bookings tab like this:

```js
bodyText.includes("Full Moon") || bodyText.includes("Nothing in your history")
```

The second half matches the empty state. So the check passed whether the tab had bookings in it or not. It reported success on a tab that was, in fact, empty. A test that cannot fail is worse than no test, because it buys you false confidence.

### 6. Small sloppiness
A leftover prop on the booking button — `icon={book.isPending ? undefined : <Loader2 className="hidden" />}` — that did nothing at all and imported an icon just to hide it. Harmless, but it is the kind of thing that ends up in a codebase when nobody reads the output.

---

## What I would tell someone doing this

The spec did more work than the prompts. Everything I had decided in advance came back close to right, and the parts I had thought hardest about — the lock, the constraints, the test class — never went wrong, because there was nothing left to guess.

The failures clustered somewhere specific: things you cannot see in a diff. An event loop. A viewport width. Whether `restart` re-reads a file. Whether a test can actually fail. Reading the code would not have found any of those. Running it found all of them, and the one that got furthest was the one where my automated check was looking in the wrong place.

If I did it again I would spend less time reviewing code as text and more time on the checks themselves — different screen sizes, and making sure each test fails when it should.
