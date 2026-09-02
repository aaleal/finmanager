# 0043 — A manual's identity is its description, not its bytes

## Context

[ADR-0040](0040-a-manual-is-downloaded-not-linked.md) dedupes instruction imports
by content hash: `store_from_url` is content-addressed, so re-downloading a file
already on disk resolves to the same `Document` and the unique constraint on
`(lego_set_model_id, document_id)` refuses the second row. Point 4 of that ADR
says pressing «Importar do Brickset» twice "adds nothing", on that assumption.

The real household inventory broke it on the first set that had more than one
manual. `10280` imports seven rows for three actual booklets — the info booklet
once, and each of the two building-instruction volumes three times over, each
repeat a *different* `Document`. Brickset's own PDF endpoint does not return
byte-identical content on every request for the same manual (most likely a
per-request artefact embedded in the file), so the content hash cannot tell a
reprint from the same file fetched again. The UI had grown a "(1/3)" suffix to
paper over exactly this, on the theory that LEGO sometimes reprints a manual
under an unchanged description — plausible, but not what was actually happening.

## Decision

`_import_instructions` now treats `description` as the manual's identity for a
given set, checked *before* the file is even downloaded.

1. A remote manual whose description already has a row for this set is skipped
   outright — no request made, no `Document` created. This also catches Brickset
   listing the same booklet twice in one response, which is what produced three
   copies of `10280`'s two volumes in a single import.
2. The content-hash check stays as a second guard for the opposite case: two
   different descriptions that happen to resolve to the same file.
3. The frontend's "(n/m)" repeat-numbering is gone. It existed only to make
   sense of a situation that should no longer arise.

## Consequences

- A genuine reprint — the same description, a deliberately different file —
  would now be silently skipped rather than kept as a second entry. Nothing in
  the real inventory shows this ever happening for LEGO's own instruction PDFs;
  if it does turn up, the fix is a name that actually differs (Brickset already
  distinguishes real revisions in the description, as `10280 V29` versus
  `10280 V39` did here), not a return to per-file identity.
- The four duplicate rows `10280` had already accumulated were removed by hand
  (kept the lowest `position` per description); every set imported before this
  fix was checked and none of the others showed the same pattern.
