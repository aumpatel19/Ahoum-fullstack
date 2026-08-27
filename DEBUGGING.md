# Debugging Log

Four issues hit while building this (the last one reported from use, not found by me). Nothing here is invented — each one has a commit or a command you can re-run. Format: **symptom → diagnosis → root cause → fix → verification**.

---

## 1. The HTTP race demo crashed before it fired a single request

**Symptom.** The unit-test race proof was green, so I moved on to the end-to-end one. The first run against the live stack died immediately:

```
$ docker compose exec backend python scripts/race_demo.py
...
  File "/app/scripts/race_demo.py", line 43, in ensure_demo_accounts
    creator, _ = User.objects.get_or_create(
django.core.exceptions.SynchronousOnlyOperation:
    You cannot call this from an async context - use a thread or sync_to_async.
```

**Diagnosis.** The traceback points at `get_or_create`, which is ordinary ORM code that works everywhere else in the project — so the problem was not the query but *where it was running*. The call chain was `asyncio.run(main())` → `main()` → `ensure_demo_accounts()`, i.e. a synchronous ORM call several frames deep inside a coroutine. Django notices it is inside a running event loop and refuses.

**Root cause.** I had structured the script as one big `async def main()` because the interesting part — firing N bookings at once — is async. Everything else got dragged into the event loop with it: creating the demo accounts, minting tokens, and the final "how many bookings actually exist" verification. Django's psycopg driver here is synchronous, so a blocking query inside the loop would stall the very concurrency the script exists to demonstrate. The guard is Django protecting me from a bug I had not noticed yet.

**Fix.** Split the script by concern rather than by convenience. `main()` is now a normal function that does all the ORM work; `run_race()` is `async` and contains nothing but HTTP. `asyncio.run()` wraps only the fan-out:

```python
def main() -> int:
    creator_token, racer_tokens = ensure_demo_accounts()      # sync ORM
    outcome = asyncio.run(run_race(creator_token, racer_tokens, starts_at))  # HTTP only
    confirmed = Booking.objects.filter(...).count()           # sync ORM
```

The module docstring now says why, so the next person does not "simplify" it back.

**Verification.** `docker compose exec backend python scripts/race_demo.py` prints 1 × HTTP 201 and 9 × HTTP 409 `sold_out`, with `confirmed == 1` and `seats_taken == 1`, and exits 0. Commit: *fix(scripts): keep every ORM call out of the event loop in race_demo*.

---

## 2. The health endpoint returned HTML — and my first diagnosis was wrong

**Symptom.** Smoke-testing the fresh Django project from a small script:

```
ValueError: Content-Type header is "text/html; charset=utf-8", not "application/json"
```

**First diagnosis (wrong).** DRF ships `BrowsableAPIRenderer` alongside `JSONRenderer`, and it renders HTML. Content negotiation picking the browsable renderer was the obvious explanation, so I pinned `DEFAULT_RENDERER_CLASSES` to JSON only and re-ran.

**Same error.** That is the useful part: the hypothesis made a prediction, the prediction failed, so the hypothesis was wrong. Instead of guessing again I printed the things I had been assuming — status code and body:

```
status 400
<!DOCTYPE html> ... <title>DisallowedHost at /api/healthz/</title>
```

**Root cause.** It was never a renderer problem. It was a 400 error page. `django.test.Client` sends `Host: testserver`, and Django's test *runner* appends `testserver` to `ALLOWED_HOSTS` in `setup_test_environment()`. I was instantiating `Client()` from a plain `python -c` script, so that setup never ran and every request was rejected before reaching the view. The HTML was Django's debug error page, and DRF was not involved at all.

**Fix.** No production change was needed — the code was correct and the harness was wrong. Real assertions moved into pytest, where `pytest-django` performs that setup for me. I kept the JSON-only renderer change on its own merits: this API is consumed by a Next.js client and by scripts, `/api/docs/` already provides a human-browsable surface, and one renderer means every response, including errors, is uniformly JSON.

**Verification.** `pytest` passes 51 tests, including `test_healthz_is_public`, and `curl http://localhost:8080/api/healthz/` through nginx returns `{"ok":true,"db":"up"}`.

**What I took from it.** The error message named a symptom (`Content-Type`) that pointed at the wrong layer entirely. Printing the raw status and body — the two things I had assumed rather than checked — found it in one step.

---

## 3. The OpenAPI schema typed the session id as a string

**Symptom.** `manage.py spectacular` was noisy:

```
Warning [SessionViewSet]: could not derive type of path parameter "id" because it is untyped
and obtaining queryset from the viewset failed. ... Defaulting to "string".
```

Harmless at runtime, but `/api/docs/` showed `id` as a string, which is exactly the kind of small wrongness that makes a reviewer distrust the rest of the document.

**Diagnosis.** drf-spectacular infers path-parameter types from the viewset's queryset model. `SessionViewSet` deliberately has no class-level `queryset` — it only has `get_queryset()`, which for write actions does `Session.objects.filter(creator=self.request.user)`. During schema generation there is no authenticated request, so that call raises and the generator falls back to `string`.

**Root cause.** The ownership design (D6: scope the queryset instead of checking permissions per object) means the queryset genuinely depends on the request. That is right for security and inconvenient for introspection.

**Fix.** Declare a class-level `queryset` purely so the generator has a model to look at, and leave `get_queryset()` in charge of every real request:

```python
# Declared so the router and the schema generator can infer the pk type;
# get_queryset() below is what actually scopes every request.
queryset = Session.objects.select_related("creator").all()
```

The risk in this fix is obvious and worth naming: if `get_queryset()` were ever removed, the class attribute would silently expose every creator's sessions to every creator.

**Verification.** `manage.py spectacular` now reports zero warnings, and the authorization tests still pass unchanged — in particular `test_creator_cannot_edit_another_creators_session` and `test_creator_cannot_delete_another_creators_session`, which both assert 404. Those tests are what makes the class attribute safe to keep: if the scoping ever regresses to the unfiltered queryset, they fail immediately with a 200 instead of a 404.

---

## 4. On a narrow window the navbar had no links at all, and the login page was a dead end

**Symptom.** Reported from actual use: "browse is not working, and when I try to sign in there's no back option."

**Diagnosis.** Browse worked fine for me at desktop width, so the first job was to reproduce rather than to start editing. I drove the app at three viewport widths and listed what was actually visible in the header:

```
=== viewport 1280px ===  navbar items: ["Ahoum","Browse","Sign in"]   Browse visible: true
=== viewport 700px  ===  navbar items: ["Ahoum","Browse","Sign in"]   Browse visible: true
=== viewport 390px  ===  navbar items: ["Ahoum","Browse","Sign in"]   Browse visible: FALSE
                          -> NO WAY BACK from /login at this width
```

The links were in the DOM at every width but not *visible* below 640px. Widening the sweep to a signed-in creator on a phone made it worse: the only visible controls were the logo and an unlabelled avatar button, and the avatar dropdown held just Profile / My bookings / Sign out — so **a creator on a phone could not reach `/creator` at all.**

**Root cause.** Two separate mistakes that happened to combine.

1. Every nav link carried `hidden … sm:inline-flex`. That is the standard "hide these on mobile" pattern, and it is only correct when something *replaces* them — a hamburger, a bottom bar, anything. Nothing did. I had written the responsive half of the pattern and skipped the half that makes it work.
2. `/login` had no navigation of its own; it borrowed the navbar's Browse link as its back button. When that link disappeared, the page became a trap — and it is a page a signed-out visitor lands on by clicking Book, which makes it exactly the wrong place to strand someone.

There was also a third, subtler contributor to "browse is not working": on the catalogue itself, the active link differed from the others only by text colour. Clicking it does nothing, because you are already there — but nothing on screen says so, which reads as a broken link.

**Fix.**
- Signed-out visitors get a labelled menu button below `sm` containing every link plus Sign in; signed-in visitors get the same links folded into the account dropdown (`sm:hidden`, so they are not duplicated on wide screens).
- `/login` got its own "Back to sessions" link and a "you don't need an account to browse" footer, so it never depends on the navbar again.
- `/onboarding/role` — the other route that can hold you in place — got a "sign out and keep browsing" escape.
- The header no longer offers "Sign in" while you are on the sign-in page.
- Active links now get a filled background and the menu marks the current page "HERE", so a link that cannot go anywhere explains itself.
- Both menus close on Escape, on outside click, and on navigation; the avatar button got an `aria-label` (it was an unlabelled button before).

**Verification.** The same probe, re-run, now enumerating what is reachable including through menus:

```
@1280 anonymous  reachable: ["Ahoum","Browse"]                                        (+ "Sign in" button)
@1280 creator    reachable: ["Ahoum","Browse","My bookings","Creator","Profile","Sign out"]   missing: nothing
@390  anonymous  reachable: ["Ahoum","Browse HERE","Sign in"]                          missing: nothing
@390  creator    reachable: ["Ahoum","Browse HERE","My bookings","Creator","Profile","Sign out"]  missing: nothing
/login in-page back links: 2, click lands on "/": true
outside click closes menu: opened=1 afterOutsideClick=0
```

Plus: a signed-in visitor to `/login` is redirected to `/` (so it has no back link because it never renders), and there is no horizontal overflow at 390px.

**What I took from it.** The bug was not in logic I could have reasoned about from the diff — it was in what a viewport 890px narrower than mine actually renders. I had screenshotted every page during the build, but only at 1280px, so the automated check that was supposed to catch UI problems was blind to the entire class of problem the user hit. Viewport width is now part of the sweep.
