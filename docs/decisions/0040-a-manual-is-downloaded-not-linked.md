# 0040 — A manual is downloaded, not linked

## Context

`getInstructions2` returns a list of `lego.com` PDF URLs for a set: the building
instructions and the printed info booklets. Showing them is one anchor tag.

An anchor tag is also the whole problem. Those URLs live on LEGO's CDN, and this
application exists because a household wants its own records on its own hardware.
A link rots when LEGO reorganises its asset paths, when a retired set's booklet
is pulled, and — the case that actually happens — on the evening the internet is
down and someone wants to rebuild a set from the shelf. A restored backup that
gives back every photograph and none of the manuals has restored half a
collection.

## Decision

A fifth table, `lego_set_instructions`, and every PDF stored locally the same way
every image already is.

1. **The bytes come down once.** The import calls `documents.store_from_url`, so
   a manual is magic-byte validated, content-addressed by SHA-256 and written
   under `STORAGE_ROOT` like any other attachment. `Document.url` stays
   provenance and is never re-fetched ([ADR-0004](0004-signed-document-urls.md)).
2. **The row carries what the file cannot**: the description Brickset printed,
   the language it is written in, and a position. Unique on `(set, document)`,
   cascade-deleted with the set — the same shape as
   [`lego_set_images`](0013-lego-set-gallery.md).
3. **The archive carries them.** `lego_backup` writes the instruction rows and
   their documents alongside the images, and the format goes to version 2. A
   version 1 archive restores unchanged: it simply has no `instructions` key.
4. **Nothing is fetched on a render.** Brickset is contacted only when someone
   presses «Importar do Brickset», which brings the additional images
   (`getAdditionalImages`) and the manuals in one press. Pressing it twice adds
   nothing: the content-addressed store recognises every file it already holds.
5. **Only PT and EN are kept**, plus every manual that carries no language at
   all. A LEGO building instruction is pictures — its description (`BI 3106,
   80+4, 10280 V29`) names no language because it needs none, and dropping it
   would leave the shelf with nothing to build from. The info booklets do name
   one (`10280_ENGB_Info_Booklet`), and a household that reads Portuguese and
   English has no use for the Simplified Chinese one.

## Consequences

- A manual is a 3–60 MB scanned book, not a 200 kB photograph, so
  `store_from_url` grew an explicit ceiling: `max_instruction_bytes` (80 MB) for
  these, the ordinary 15 MB upload limit for everything else. The download is
  streamed and abandoned the moment it crosses the ceiling, so an oversized file
  is never buffered whole.
- The storage volume grows by roughly the size of the collection's manuals. That
  is the price of the guarantee, and it is paid once per distinct file — two sets
  sharing a booklet share one copy on disk.
- The PDFs are served through the existing signed, time-limited document route,
  which already answers `Content-Disposition: inline`, so a manual opens in a new
  browser tab and never leaves the machine.
- A manual that fails to download is skipped, not fatal: an import that gets 11
  of 13 files is worth more than one that rolls back.
