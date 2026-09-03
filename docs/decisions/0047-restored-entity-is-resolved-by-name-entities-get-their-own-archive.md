# 0047 — A restored row's entity is resolved by name, and entities get their own archive

## Context

The LEGO backup archive (ADR-0032) rewrote every model's and instance's
`entity_id` onto whichever single entity the caller chose when restoring —
useful for "move my collection to a new install", but wrong the moment a
collection is not one person's: five sets bought by Ana and five by Bruno
came back, on any other installation, all attributed to whoever happened to
run the import. ADR-0007 already rejects exactly this shape of mistake for a
live write ("silently attributing a €600 purchase to the wrong person is
worse than an error message"); a restore should not get a pass a normal write
does not.

A name, unlike a UUID, is something the household already uses to tell its
entities apart, and is the one thing about an entity that is meaningful on an
installation that has never seen it before.

## Decision

- The LEGO archive now carries the owning entity's **name** on every model and
  instance row, in addition to its own id. Restoring resolves that name
  against the target household's entities and refuses — does not guess — a
  name nothing there matches, pointing at the fix (import the entities
  archive first). An archive written before this (v1/v2) carries no name, and
  its rows fall back to the entity the caller chose, exactly as before.
- A new, small backup module, **`entities`**, exports a household's entities —
  `name` and `color`, plus each member's `display_name`/`email` as a
  **read-only reference** — and restores by creating whichever names the
  target household does not already have. An existing name is matched, not
  renamed or merged, the same rule every other module's restore already
  follows. `member_ids` itself is never restored (points at users, which do
  not exist yet on a fresh install) and no `User` or password is ever created
  by this: `POST /setup` and an OWNER's own `POST /household/members` remain
  the only two places an account is created (ADR-0011, ADR-0014) — a restore
  only requires `Writer`, so letting it create accounts would let a MEMBER
  grant a login to anyone.
- The module registry (`backup_service.modules()`) lists `entities` before
  `lego`. A global "back up everything" restore walks the registry in order,
  so by the time LEGO's own rows try to resolve an entity by name, that
  entity already exists.
- **Restoring no longer requires an entity to be selected first.** Every
  restore path (`POST /settings/backup`, `backup_service.restore_any`, and
  each module's own `restore_archive`) takes the caller's `household_id`
  directly rather than resolving one specific entity — there usually is
  nothing to attribute a restore itself to. An entity (the active selector,
  or an explicit id) is only consulted as `fallback_entity_id`, and only used
  when a legacy (v1/v2) row has no name to resolve. `resolve_optional_entity`
  (`deps.py`) is `resolve_write_entity`'s sibling for exactly this shape: it
  validates an entity when one is given, but returns `None` instead of
  refusing «todas» when nothing needs one.

## Consequences

- Importing a mixed-ownership collection now needs one extra step — import
  the entities archive (or the global one, which includes it) before or
  alongside LEGO's — but the alternative was silent misattribution, which is
  not an acceptable default.
- A membership-empty entity created this way is not automatically flagged
  `is_readonly`; an owner adds its real members afterwards through the
  ordinary entity edit screen, using the members reference in the archive to
  know who to invite.
- LEGO's per-row entity resolution and the entities module share nothing but
  a convention (match by name, refuse otherwise) — neither file reads the
  other's archive shape, matching ADR-0037.
