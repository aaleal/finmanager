# 0004 — Signed, time-limited attachment URLs

## Context

Attachments (receipt scans, LEGO cover images and copy photos) must be stored
outside any web root and served only through a signed, time-limited URL — an
explicit OWASP rubric item. But the browser fetches images with `<img src>`, which
cannot attach an `X-CSRF-Token` header and, for a cross-context load, may not attach
the session cookie either.

## Decision

`GET /api/documents/{id}/content?expires=<unix>&signature=<hmac>` is deliberately
**not** behind the session dependency. The HMAC-SHA256 signature over
`"{document_id}:{expires_at}"`, keyed by `SECRET_KEY`, *is* the authorisation.

- URLs are minted server-side inside the JSON payload of an already-authenticated
  request (`image_url`, `photo_url`), never constructed by the client.
- Default lifetime is 15 minutes (`Document.signed_url_expires_minutes`).
- Verification fails closed on expiry, on a tampered signature and on a mismatched
  document id, and is compared in constant time.
- Responses carry `Cache-Control: private`, `Content-Disposition: inline` and
  `X-Content-Type-Options: nosniff`.
- Files are content-addressed by SHA-256 and fanned out by hash prefix; the resolved
  path is re-checked against `STORAGE_ROOT` as defence in depth against traversal.

## Consequences

- A leaked URL grants read access to exactly one document for at most 15 minutes.
- Browser caching still works within that window, so a grid of thumbnails is not
  re-fetched on every render.
- Because URLs expire, the frontend must not persist them; every payload carries a
  freshly signed URL. Rotating `SECRET_KEY` invalidates all outstanding links, which
  is the desired behaviour.
