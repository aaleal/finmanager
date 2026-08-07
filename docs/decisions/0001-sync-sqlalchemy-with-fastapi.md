# 0001 — Synchronous SQLAlchemy behind FastAPI

## Context

FastAPI is async-first and the obvious reflex is `AsyncSession` everywhere. But the
same domain code has to run in three places: HTTP handlers, Celery tasks and the
seed/CLI scripts. Celery is synchronous, so an async-only data layer forces either a
duplicated sync path or an event-loop bridge in every worker task. The workload is
also a four-person household on a NAS — the bottleneck will never be connection
concurrency.

## Decision

Use **synchronous** SQLAlchemy 2.0 sessions throughout, and write route bodies as
plain `def` functions. FastAPI runs those in its worker threadpool automatically.
One transaction per request, opened and closed by the `get_db` dependency;
`session_scope()` provides the same guarantees to workers and scripts.

Async is used only where it is genuinely async: Starlette middleware and the two
`UploadFile` handlers, which must `await file.read()`.

## Consequences

- The service layer is callable from a route, a Celery task, a test and a REPL with
  no adaptation. `app/services/lego_service.py` has no framework imports at all.
- No `greenlet`/`asyncio` bridging bugs, no accidental blocking calls inside an
  event loop.
- Throughput is bounded by the threadpool (40 threads by default) rather than by an
  event loop. Far beyond what this deployment needs; revisit only if a module
  introduces genuinely IO-bound fan-out.
- Provider calls (Brickset, remote image fetch) use synchronous `httpx.Client` with
  an explicit timeout, so they occupy a worker thread rather than an event loop.
