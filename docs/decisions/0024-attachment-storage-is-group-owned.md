# 0024 — The attachment volume is shared by two users, so it is group-owned

## Context

Uploading any invoice failed with
`PermissionError: /var/lib/finmanager/storage/34/f5`, before a `ProcessingJob`
existed — so there was nothing in `last_error` to read, and the crown-jewel
flow (upload → parse → review) could not be demonstrated at all.

The cause is not in the ingestion pipeline. One named volume, `storage-data`, is
mounted by containers that run as **two different users**:

- the runtime image serves requests as `finmanager` (uid 10001), non-root by
  design (OWASP);
- `./fm seed`, `./fm check` and the whole dev overlay run as **root** against a
  bind-mounted source tree, because under rootless Podman container-root is what
  maps to the host user that owns the checkout.

Whichever container wrote a hash shard first owned it. Seeding created
`storage/34/f5` as `root:root 0755`, and from then on the API could not create a
file inside it. Every upload died, for every file type.

## Decision

The storage tree is **group-owned by `finmanager` and group-writable**, and no
process that writes to it may leave a shard only its own uid can use.

Three parts, deliberately overlapping:

1. The `finmanager` user and group are created in the **base** image stage, so
   dev and runtime agree on uid/gid 10001. The storage root is `root:finmanager`
   mode `2775` — setgid, so a new shard inherits the group whoever creates it.
2. `docker-entrypoint.sh` sets `umask 002`, reconciles the tree when it starts as
   root, and then **drops privileges** with `setpriv` before `alembic` or
   `uvicorn`/`celery` run. The container starts as root; nothing that serves a
   request stays root.
3. `documents.store_bytes` — the one code path every attachment goes through —
   creates its shards `2775` and its files `0664`, re-applying the mode even to a
   directory that already exists.

## Consequences

- Part 3 is what makes this robust rather than merely fixed. One-shot commands
  (`./fm seed`, `./fm check`) *replace* the container command, so the entrypoint
  never runs for them; relying on the umask alone would have left the same bug
  one `podman-compose run` away. The storage layer owns its own permissions.
- The runtime container no longer declares `USER finmanager`. That reads like a
  regression and is not: it is the standard init pattern (the Postgres and Redis
  images do the same). `ps` inside a running container shows `uvicorn` and
  `celery` at uid 10001, and the root window is a `chown` and a `chmod`.
- An installation whose volume was already poisoned repairs itself on the next
  API start, without a `reset` and without losing a document.
- `tests/integration/test_document_storage_permissions.py` asserts the invariant
  directly: a stored document is group-writable and its shards are setgid. It is
  a filesystem test rather than an HTTP one on purpose — the failure it guards
  against happened *before* any application state existed.
