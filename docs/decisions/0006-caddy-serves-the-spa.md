# 0006 — The web container *is* Caddy

## Context

The brief specifies Caddy in front of the stack. The obvious shape is four services
— `caddy`, `web`, `api`, `db` — but a single-page app has no runtime: it is a folder
of hashed static files. A separate `web` service would exist only to hand that
folder to Caddy through a shared volume, which introduces a build-order dependency
and a volume that must be re-populated on every deploy.

## Decision

`apps/web/Dockerfile` is a multi-stage build whose final stage is `caddy:2-alpine`
with the built `dist/` copied in and a `Caddyfile` that:

- serves the SPA with `try_files {path} /index.html`,
- caches `/assets/*` immutably for a year and `index.html` not at all,
- reverse-proxies `/api/*` to `api:8000`,
- sets `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy`, and strips
  the `Server` header.

The development overlay replaces this service with the Vite dev server, which
proxies `/api` to the same place.

## Consequences

- One published port (8080) and one fewer service to reason about.
- The browser origin is identical in development and production, so `SameSite=Lax`
  cookies and same-origin fetches behave the same in both — no CORS in production at
  all (it is enabled only when `APP_ENV=development`).
- Rebuilding the frontend rebuilds the proxy image. Acceptable: the image is tiny and
  the two always ship together.
- TLS is intentionally left off (`auto_https off`) and the site binds plain `:8080`.
  The deployment target is a NAS reached over LAN or VPN, usually behind the NAS's own
  reverse proxy. To let Caddy terminate TLS itself, replace the `:8080` site address
  with a real hostname and drop `auto_https off`.
