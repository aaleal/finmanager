# 0049 — Brickset images and manuals are fetched in the background, not inline

## Context

Registering a genuinely new set (bulk import or the manual "Adicionar
conjunto" form) does two very different kinds of work once Brickset confirms
the set number: writing the catalogue fields Brickset already returned in
that one lookup (name, theme, dates, piece count, RRP, ...) — fast, local —
and then `import_from_brickset` (ADR-0040), which pulls every extra
photograph and every manual down as its own HTTP download, one at a time,
synchronously, before the caller ever gets a response. A set with a dozen
photos and a couple of manuals can take minutes if Brickset's asset host is
slow or briefly unreachable — and bulk import, which by definition mostly
adds sets the household has never registered before, pays this cost on
almost every row. Reported symptoms: a single "Guardar cópia" hanging for a
long time, and a batch import appearing to freeze forever on "a importar 0
de 1" — both traced to this same synchronous fetch, not to a broken import.

The catalogue lookup itself was never the problem — it stayed fast and
confirmed Brickset was reachable in every report. Only the asset downloads
that follow it are slow.

## Decision

**Registering a copy (single or bulk) no longer waits for images or
manuals.** `queue_brickset_assets` (`lego_brickset_jobs.py`) replaces the
inline call to `import_from_brickset` at both automatic trigger points (the
manual add-set dialog, and a new row in bulk import): it only writes two
`ProcessingJob` rows (one per asset type) and dispatches them to the existing
Celery worker (provisioned since Phase 0, unused until now) — no network
call, so it's as fast as any other write in the request.

**Images and manuals are two independent jobs, not one.** A set with broken
manual links but working photos (or vice versa) shows exactly that instead of
an all-or-nothing result. Each job is a `ProcessingJob` row the user can see,
cancel (cooperative — checked between each remote item, so an in-flight
60-second download still finishes) and retry (resets to `QUEUED` and
re-dispatches) via `GET/POST /lego/brickset-jobs*` and the "Processos
Brickset" panel.

**Re-triggering an already-active job reuses it instead of double-queueing.**
Keyed by `idempotency_key = f"{job_type}:{model_id}"` — calling
`queue_brickset_assets` twice for the same model (e.g. bulk import retrying a
row) is a no-op if that model's job is still queued or running.

**The synchronous `import_from_brickset` service function and its
`POST /models/{id}/brickset` endpoint are unchanged.** Nothing calls the
endpoint automatically any more (ADR-0044 already removed its UI button), but
the function itself, and the split-out
`import_model_images_from_brickset`/`import_model_instructions_from_brickset`
it's built from, are exactly what the two background jobs call — a job is
just that same work running on the worker instead of the request thread.

## Consequences

- `ProcessingJob.status` gained `CANCELLED` (migration
  `c3f8a1d92e56`) — the first status a user, not just the job itself, can set.
- A new set's cover photo and catalogue fields appear immediately; its extra
  gallery photos and manuals appear moments to minutes later, whenever the
  worker gets to them. This is a visible, intentional change in when a set
  "looks complete" — not a bug if a fresh set briefly has no gallery yet.
- Bulk import's per-row NDJSON result now reports success as soon as the copy
  itself is registered — it says nothing about whether that set's photos and
  manuals actually arrived. The jobs panel is the only place that shows it.
- The worker is a different process (and, in dev, a different container)
  than the API, so `queue_brickset_assets` commits before dispatching —
  there is no shared, not-yet-committed transaction for it to piggyback on.
