# 0011 — First-run setup instead of seeded credentials

## Context

Until now the only way to obtain an account was `make seed`, which created three
demo users and printed `owner@finmanager.local / finmanager`. That is fine for a
developer and wrong for the household this application is actually for:

- A real installation had to run the *demo dataset* to get a login, then delete
  the demo data around itself.
- The default password lived in `.env.example`, `docker-compose.yml` and the
  README. Every clean install was briefly reachable with credentials published in
  the repository, and stayed that way until someone remembered to change them.
- `docker-entrypoint.sh` runs migrations and starts uvicorn. Nothing in the boot
  path creates a user, so an operator who skipped the seed got a login form for
  an account that did not exist and no error explaining why.

The alternatives were: keep seeding an owner and force a password change on first
login; create an owner from environment variables at boot; or let the application
ask.

## Decision

The application asks, once.

1. **No account ships with the product.** `BOOTSTRAP_OWNER_EMAIL` /
   `BOOTSTRAP_OWNER_PASSWORD` were kept at first as input to the opt-in demo seed,
   and later deleted outright when the seed stopped creating users
   ([ADR-0014](0014-seed-creates-no-users.md)). A production install never has a
   default password to rotate.
2. **`POST /setup` is the only unauthenticated write in the API,** and only while
   the database has no non-deleted `User`. It creates the household, the first
   `OWNER`, their membership, their single-member entity and the default
   settings, then returns a normal session.
3. **The guard is transactional, not advisory.** `GET /setup/status` exists so the
   SPA can choose a screen, but the count is re-checked inside the writing
   transaction. Two people racing the form produce one owner and one `409`.
4. **The owner is signed in on success.** They chose the password seconds ago;
   `must_change_password` is `false` and there is no second form to fill.
5. **It never re-opens.** There is no environment flag to reset it. M7 already
   refuses to remove the last `OWNER`, so a live installation cannot fall back
   into the setup state.

Env-var bootstrapping was rejected for the same reason as the seeded owner: it
puts a password in a file on disk, in shell history, and in `docker inspect`.

## Consequences

- `docker compose up` on an empty volume reaches a usable application through the
  browser alone. The seed becomes what it always should have been: a developer
  convenience.
- The window in which a fresh install is reachable with a known password closes
  completely, rather than narrowing.
- The setup password floor is 12 characters, higher than the 8 required of
  invited members, because this is the one account no one else can reset from
  inside the application.
- `POST /setup` carries no CSRF token — there is no session to double-submit
  against. It is defended by the one-shot guard and by the tightest budget in the
  rate-limit table instead.
- The SPA pays one extra request per unauthenticated boot. A configured
  installation answers it with `needs_setup: false` and caches it for the session.
- Restoring a database backup restores its users with it, so setup stays closed —
  which is the correct behaviour, and worth stating because it means a lost owner
  password is a restore-or-shell problem, not a setup problem.
