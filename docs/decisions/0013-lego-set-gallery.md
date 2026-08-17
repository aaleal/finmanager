# 0013 — The LEGO set gallery is worth a fourth table

## Context

M9 is explicit that the module is three tables — `LegoSetModel`, `LegoSetInstance`,
`StorageLocation` — and that there are deliberately **no galleries**. One
`image_document_id` per set, one `photo_document_id` per copy, and nothing else.

That held while the seed generated a coloured tile per theme. Once the seed started
downloading the real box art, the limit started costing something: a box shot
identifies a set on a shelf, but it answers none of the questions a collector
actually opens the sheet to ask — what the built model looks like, what is on the
back of the box, how many minifigures come with it.

The options were: keep one image and let the user pick which one; store an ordered
list of document IDs in a JSONB column on the set; or add a table.

## Decision

A fourth table, `lego_set_images`.

1. **The cover does not move.** `LegoSetModel.image_document_id` stays exactly where
   it was and keeps meaning "the box". Every existing reader — the grid thumbnail,
   the export, the dashboard — is untouched, and a set with no gallery behaves
   precisely as before.
2. **`lego_set_images` holds only the extra views**: a FK to the set, a FK to
   `Document`, an integer `position` and an optional `caption`. Unique on
   `(set, document)`, cascade-deleted with the set.
3. **Promotion is a swap, not a copy.** Making a gallery image the cover pushes the
   previous cover back into the gallery, so no image is ever lost by reordering and
   there is only ever one box shot.
4. **The carousel is assembled on read**, in this order: the copy's own photograph
   (it is *this* box, not the catalog's), then the cover, then the gallery by
   position. Nothing about that order is persisted.

A JSONB array of document IDs was rejected: it cannot carry a foreign key, so
nothing would stop it pointing at a deleted document, and ordering edits would mean
rewriting the whole array under a lost-update race. The table costs one migration
and buys referential integrity.

## Consequences

- M9's "three tables only" is now "four", and this file is the reason. The
  constraint was about refusing *speculative* structure; a gallery the user asked
  for with images already on disk is not speculative.
- `Document` rows are content-addressed and shared, so deleting a gallery entry
  removes the link, never the file. Two sets can point at the same image.
- The seed fills the gallery from Brickset's additional-image URLs — downloaded once
  and stored locally like any other web image, never hotlinked. Sets Brickset has no
  extra photographs of simply have a one-frame carousel, which renders as a plain
  image with no arrows.
- Ordering is an integer the user changes by promoting; there is no drag-and-drop
  and no `PATCH position` in the UI yet. The column is there when that is wanted.
