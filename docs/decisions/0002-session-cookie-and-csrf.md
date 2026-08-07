# 0002 — Server-side sessions, cookie auth and double-submit CSRF

## Context

M7 FR-7.8 requires a server-side session in Redis, an httpOnly `SameSite=Lax`
cookie, and a CSRF token on state-changing requests. Sessions must be revocable on
logout, on password change and on member departure — which a stateless JWT cannot
do without a blocklist that is, in practice, a session table with extra steps.

## Decision

- The `sessions` table is **authoritative**; Redis is a read-through cache keyed by
  the SHA-256 hash of the cookie token, with a TTL matching the session.
- The cookie stores a 256-bit random token; only its hash is persisted, so a database
  leak does not yield usable sessions.
- Unsafe methods must echo `Session.csrf_token` in an `X-CSRF-Token` header
  (double-submit). It is compared with `hmac.compare_digest`.
- The CSRF token is **rotated on every entity switch**, which is also the natural
  moment the client refreshes its copy.
- Expiry slides forward on use, but writes at most once per day to avoid a database
  write on every request.

## Consequences

- Logout, password change and departure are genuinely immediate: the row is revoked
  and the cache key deleted in the same transaction.
- `<img src>` cannot send a CSRF header, so attachments needed a different
  authorisation mechanism — see [ADR 0004](0004-signed-document-urls.md).
- The frontend keeps the CSRF token in memory only (never in `localStorage`), so an
  XSS payload cannot read it from storage.
- Rate limiting on `/auth/login` and `/auth/password` is applied in middleware and
  fails open, so Redis being unavailable degrades the limiter rather than the login.
