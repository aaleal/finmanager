# 0044 — The sheet doesn't re-run Brickset; it takes a manual by hand instead

## Context

`import_from_brickset` runs in exactly one automatic place: `add-set-dialog.tsx`
fires it once, right after a set is created from a successful Brickset lookup.
That single press already brings down every additional photograph and every
manual the API offers.

The detail sheet also carried its own «Importar do Brickset» button, next to the
manuals list, so a household could press it again later. In practice this
button answered no question the automatic import had not already answered: for
a set that came from a lookup, everything is already there; for a set that
did not (Brickset was off, the lookup found nothing, or a MOC), a network call
to a third party is not the fix for a manual the household already owns as a
paper booklet or a PDF on its own drive.

## Decision

The manual re-import trigger is gone from the sheet. In its place, instruction
manuals get the same "add by hand" path images already had: `POST
/lego/models/{id}/instructions` accepts a description plus either a URL or an
uploaded file, and stores it exactly like a Brickset-sourced manual — content
validated, content-addressed, carried by the backup. It refuses a description
already used for this set, the same rule ADR-0043 gave the automatic import.

## Consequences

- Brickset is now contacted from exactly one place in the whole application:
  the lookup at set creation. Nothing in the detail sheet makes a network call
  to a third party any more.
- A set that missed its automatic import (Brickset was disabled at the time, or
  the lookup found nothing) has no way to backfill *photographs* from Brickset
  after the fact — only manuals gained a manual path, because that was the gap
  actually in front of a real user. Gallery images already had one (the
  existing add-by-file/URL control in «Galeria do conjunto»).
- A household's own scan is now first-class: nothing distinguishes a
  hand-added manual from one Brickset supplied, in storage or in the UI.
