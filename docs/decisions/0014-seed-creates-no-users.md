# 0014 — The demo seed no longer creates users

## Context

[ADR-0011](0011-first-run-setup-over-seeded-credentials.md) removed the seeded owner
from *installation*: a clean stack asks the browser to create the first owner and
ships no default password. But `make seed` still created its own cast — Ana, Bruno
and Clara, with `BOOTSTRAP_OWNER_PASSWORD` — and four entities to hang the demo data
on.

So a real household that ran the seed to look at the LEGO module ended up with three
strangers in "Agregado", two of whom could log in with a password documented in the
repository. The door ADR-0011 closed had a second one behind it.

## Decision

The seed attaches to what is already there and creates no identity of any kind.

1. **`resolve_target` replaces `seed_household`.** It reads the oldest household and
   its oldest entity, and refuses with a plain-Portuguese message if the install has
   never been configured. The seed is now something you run *after* your first
   login, not instead of it.
2. **Everything lands on the owner's own entity.** The demo used a joint entity for
   the collection and a child's entity for the MOC; both are gone, along with the
   people they implied.
3. **`BOOTSTRAP_OWNER_EMAIL`, `BOOTSTRAP_OWNER_PASSWORD` and
   `BOOTSTRAP_HOUSEHOLD_NAME` are deleted** from the settings object, the compose
   file and `.env.example`. They no longer have a meaning to keep.
4. **Password recovery becomes explicit rather than implicit.** With no seeded
   account there is no back door, so the two legitimate routes are stated: an owner
   sets any member's password from "Agregado", and `./fm passwd <email>` does it
   from the host when the owner's own password is the one that is lost.

## Consequences

- The demo dataset is reference data and a LEGO collection. It is no longer a way
  into the application, and cannot be mistaken for one.
- Running the seed on a real household is now merely untidy rather than a security
  problem: it adds merchants, a category taxonomy and 100 LEGO sets to *your* entity.
- Tests that wanted an owner already built one through fixtures, so nothing in the
  suite depended on the seeded cast.
- The only remaining authority over a forgotten owner password is shell access to
  the server. That is the correct answer for a self-hosted application with no
  email, and it is now a documented command instead of a `psql` session.
