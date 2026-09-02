# 0045 — The table image is per copy, the star is per set, and nothing moves

## Context

[ADR-0042](0042-gallery-order-is-drag-and-drop-and-position-zero-is-the-cover.md)
made the gallery's order itself the way to choose the box shot: drag an image to
the front, and it becomes the cover, demoting whatever was there before into the
gallery. Living with it surfaced three problems.

First, drag-and-drop earned its keep only if reordering mattered beyond picking
a cover, and it didn't — nobody needed the third photo to sit before the second.
The star it replaced did the one thing that actually mattered in one click.

Second, the cover is a property of the *set*, shared by every copy. A household
with three copies of the same set — one sealed, one built, one missing a corner
— has exactly one `LegoSetModel.image_document_id` between them, so the
collection table showed the same thumbnail for all three, defeating the whole
point of a thumbnail column: telling copies apart at a glance.

Third, and the one that took two iterations to see clearly: *even a star* moved
things around, because "promote" was built as a swap — delete the image's
gallery row, write it into `image_document_id`, and push whatever was there
before into a freshly created row at the end of the gallery. Picking a new cover
made it visibly jump to the front of the editor and pushed the old one to the
back. Nobody asked for that; they asked for a mark, not a move.

## Decision

Two separate pickers at two separate scopes, and a promotion that changes a
pointer without moving a single row.

1. **Order goes back to append-only.** `position` still exists and still orders
   the gallery, but nothing in the UI changes it. A new image lands at the end;
   nothing about deleting or promoting another one moves anything else.
2. **Promoting a gallery image no longer deletes its row.**
   `promote_model_image` now does exactly one thing to the chosen image: point
   `model.image_document_id` at its document. The image's `LegoSetImage` row —
   its `id`, its `position` — is untouched. The *previous* cover is appended to
   the gallery only if it is not already sitting there (which, after the first
   promotion in a set's life, it usually already is — every image ever promoted
   stays exactly where it was). Nothing is ever lost and nothing not directly
   involved ever reorders.
3. **A document can be the cover and a gallery row at once.** `frames()` (the
   client-side helper that assembles cover + gallery into one ordered list) now
   checks whether the cover's document already appears among the gallery images
   and, if so, skips adding a second, duplicate leading frame for it — the image
   is only ever shown once, at its own place in the gallery, just flagged
   `isCover`.
4. **The star is back**, in «Galeria do conjunto» only. A filled, always-visible
   star marks whichever tile `isCover`; hovering any other tile reveals an
   outline star that promotes it. Trash still hides on the one frame that has
   no row to delete — the set's very first box shot, before it has ever been
   superseded.
5. **A copy can pick its own table image**, independently of the set's cover.
   `LegoSetInstance.display_image_document_id` is a plain FK to any `Document`
   already reachable from the set (its cover or any gallery entry) — validated
   server-side against exactly that set. `PUT /lego/instances/{id}/display-image`
   sets or clears it. The picker lives on «Editar cópia»: one tile grid, click
   to choose, click the active tile again to clear back to the set's default.
   The table's fallback chain grows one link: a copy's own uploaded photograph
   beats its `display_image`, which beats the set's cover.
6. **The header shows one image, not a strip.** The detail sheet's header
   carousel dropped its inline thumbnail row entirely: it shows the lead
   frame — the copy's own photo if there is one, otherwise whichever frame
   `isCover` — with arrows to step through the rest and a click to open the
   full-screen lightbox. The lightbox keeps a thumbnail row, in a single
   horizontally-scrolling line (a mouse wheel is redirected sideways there, since
   the row never grows tall enough to need vertical scroll); "Galeria do
   conjunto" is the only place that still shows a capped, expandable grid.

## Consequences

- `display_image_document_id` is validated against the set's cover and gallery
  document ids on every write, so a copy can never point at another set's image
  even if a client sent an arbitrary id.
- Promoting a second, then a third image never shrinks the gallery: every image
  that has ever been the cover stays visible, either as the current cover or as
  an ordinary gallery row — the only thing that changes on a promotion is which
  one is flagged.
- The header carousel's default frame is no longer "whatever index zero is" —
  `SetCarousel` computes it (photo, else the `isCover` frame) and re-syncs
  whenever it changes, so starring a new cover elsewhere on the same sheet
  updates the header without the user touching it.
- «Editar conjunto» and the header no longer offer any drag-to-reorder affordance
  at all; the only place order was ever meant to be *decided* — which image is
  the cover — is a single click now, and only that.

