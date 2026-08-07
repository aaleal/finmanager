# 0007 — Entity is attribution, not permission

## Context

Every record in every module carries an `entity_id`. The tempting reading is that an
entity is a security boundary — "Ana cannot see Bruno's data". M7 FR-7.3 and its
Open Questions table reject that explicitly: this is a four-person household that
already shares a bank account, and per-entity read isolation "buys nothing but
bugs".

## Decision

- **Reads:** any authenticated household member reads every entity's data. The
  entity selector narrows the *view*, it never enforces access. Query scoping lives
  in one helper (`_scope`) that filters to the active entity, or to every entity in
  the household when the selector is on «todas».
- **Writes:** governed by role only — `OWNER` and `MEMBER` write, `VIEWER` does not.
  Enforced at exactly two places: `require_write` and `require_owner`.
- **Attribution:** a new record must name its owning entity. When the selector is on
  «todas» the request is **refused**, not guessed
  (`resolve_write_entity`), because silently attributing a €600 purchase to the wrong
  person is worse than an error message. The add dialog answers this by asking for
  the entity inline.
- **Re-attribution** is an ordinary field edit, audited like any other — no approval
  workflow, no dedicated table.

## Consequences

- The security boundary is authentication. An unauthenticated request sees nothing;
  there is exactly one household per deployment.
- No `PermissionOverride` table, no visibility computation, no per-module ACL.
- If real isolation is ever needed it is added in `_scope` and in `deps.py` and
  nowhere else — every module already carries `entity_id`.
- Entities that lose their only member become `is_readonly` rather than disappearing,
  so their history stays readable (M7 FR-7.6).
