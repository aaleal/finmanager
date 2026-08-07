# 0003 — `VARCHAR` + `CHECK` instead of Postgres `ENUM`

## Context

The brief (§3, Backend/data) says to prefer lookup tables for externally visible,
evolving enums and to reserve Postgres `ENUM` for internal, rarely changing codes.
Most of this system's enums are externally visible: `ownership_status`, `link_type`,
`processing_status`, `condition`, `build_state`, merchant kinds, category domains.

## Decision

Store them as `VARCHAR` columns with a named `CHECK` constraint listing the allowed
values, and mirror the allow-list as a module-level tuple in `app/models/`. Pydantic
`Literal` types carry the same list to the API contract.

A real lookup **table** is reserved for the case where a value needs attributes of
its own (a display name, an ordering, a colour). None of the Phase 0/1 enums do.

## Consequences

- Adding a value is `ALTER TABLE … DROP CONSTRAINT … ADD CONSTRAINT …` in a
  migration: fast, reversible and reviewable. Postgres `ENUM` alteration is neither
  transactional nor reversible in the same way.
- The database still rejects garbage — this is not "just a string column".
- The allow-list exists in three places (DB constraint, SQLAlchemy tuple, Pydantic
  `Literal`). That duplication is deliberate: each layer must be able to reject a bad
  value on its own. Keep them in sync when adding a value; the integration tests will
  catch a mismatch on the paths that matter.
