# 62. Demo data is packaged; the household's own data is mounted

Date: 2026-09-13

## Status

Accepted. Supersedes ADR-0060's placement rule and narrows ADR-0027.

## Context

Three unrelated kinds of file had collected into two folders named after neither
of them:

- `app/data/` held the grocery taxonomy and the attribute vocabulary — reference
  data, identical for every install (ADR-0029) — and, alone among them, one
  gitignored household workbook.
- `app/seed/` held the demo code, *and* 58 MB of this household's real LEGO box
  art, *and* its real LEGO inventory, *and* its eleven real *talões* — all
  committed, under a name that says "demonstration".

So the same household's data was gitignored in one folder (the catalogue built
from its purchase history) and committed in the other (the *talões* that history
came from). ADR-0060 drew the line at "source material is private, derived data
is public", and ADR-0027 kept the *talões* public as the parser corpus, but a
receipt is not less personal for being an input, and the LEGO images and
inventory were never covered by either argument at all.

The practical cost was the one that forced this: the API image is built by
copying `apps/api/` in. Anything inside the package is frozen at build time, so
replacing the catalogue with a newer export meant rebuilding an image, and the
box art was 58 MB of every clone and every layer.

## Decision

Split by *who the file belongs to*, and let that decide where it lives.

**Reference data stays packaged**, unchanged: `apps/api/app/data/`. Shipped with
the release, same bytes for everyone, ensured or loaded on demand (ADR-0029,
ADR-0057).

**Demo data is packaged and committed**, in `apps/api/app/demo/` — the renamed
`app/seed`. It is entirely invented: seven LEGO sets that exist to exercise a
sale, a gift with no cost basis, a MOC, missing parts and a future retirement
date; one receipt whose arithmetic is worth reading; four tags. It moved out of
Python literals into `app/demo/data/*.json`, one file per module, so the demo
dataset can be read and extended without reading the loader.

**The household's own files are mounted, never committed**: repo-root `data/`,
bind-mounted read-only at `/var/lib/finmanager/defaults` (`DEFAULTS_ROOT`).
`app/core/defaults.py` is the single manifest naming each one. Every path is
optional — absent means "nothing to load yet", never an error — which is what
makes a public clone, a fresh install and this household the same code path.

The *talões* move there with the rest. The parser tests skip when the corpus is
absent (`tests/corpus.py`) rather than failing.

The one-off network fetch, `download_images.py`, moved to
`dev/download-lego-images.py`: it imports nothing from `app`, nothing the app
serves calls it, and it is the same species as `dev/build-product-seed.py`.
`images.py` stayed, because the seed imports it at runtime to draw placeholders.

## Consequences

- Replacing a default is dropping a file in. No rebuild, no migration, no code
  change — which is the whole point, and was not true before.
- The repository loses 58 MB and stops publishing eleven of someone's receipts.
- **CI loses the parser corpus.** The golden extraction files still pin the
  extractor, but the eleven end-to-end reconciliation assertions only run where
  the receipts are mounted. Producing an anonymised corpus is real work and is
  deliberately not done here; until it is, those tests are a local guarantee,
  not a shared one.
- `make seed` no longer loads a LEGO collection on a clone that is not this
  household's — it loads the seven demo sets and stops. That is the correct
  behaviour and was previously masked.
- A default the household edits after loading does not change what was loaded.
  The mount is read-only and the database holds a copy; re-pressing the button
  is the way to reconcile, and every loader is additive.
