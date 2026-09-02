# 0042 — Gallery order is drag-and-drop, and position zero is the cover

## Context

[ADR-0013](0013-lego-set-gallery.md) shipped the gallery with exactly one way to
change order: promote a gallery image to the box shot, which pushes the previous
cover to the back of the gallery. Its last line said the rest plainly: *"there is
no drag-and-drop and no `PATCH position` in the UI yet. The column is there when
that is wanted."* [Module 9.3](../../00.prompts/modules/09.3-lego-grid-and-gallery.md)
deferred it explicitly for the same reason — the column existed, nothing called it.

Using the collection with 90-odd real sets rather than seven made the star button
worth replacing. "Tornar principal" was the only ordering control at all: it could
put an image first, never put it third, and it duplicated a second, near-identical
gallery editor tucked inside «Editar conjunto». A summary page dense enough to
need two rows of thumbnails also needed one editor, not two.

## Decision

One reorderable list, dragged into place, with no separate "make this the cover"
action — the box shot is simply whichever image the user leaves at the front.

1. **The list is assembled the same way the carousel already is.** `frames()`
   already puts the cover first and the gallery after, in position order; the
   editor drags entries within that same list instead of maintaining a second
   view of it.
2. **Index zero is arrived at, not chosen.** Dragging any image to the front
   calls the existing `POST …/images/{id}/cover` — the same promotion endpoint
   ADR-0013 shipped, now reached by drop instead of by a star. Everything else
   is a `PATCH …/images/{id}` with the new `position`. No endpoint changed.
3. **The demoted cover keeps ADR-0013's behaviour**: it lands at the end of the
   gallery, not at the exact slot vacated by the image that replaced it. A
   second drag moves it precisely if that matters; the alternative — teaching
   the client to guess the freshly created row's id ahead of the server — was
   worse than a two-step correction.
4. **The one editor lives on the summary tab, collapsed by default.** «Editar
   conjunto» no longer carries its own copy. A viewer without write access still
   sees the same thumbnails, just without the drag handles or the delete button.
5. **Never more than two rows.** However many images a set has, the grid shows
   only what fits two rows at the container's current width (measured with a
   `ResizeObserver`, not a fixed breakpoint table) and folds the rest behind a
   generic "+N" tile — the full set is already one click away in the carousel
   above, so the editor does not need to repeat it.

## Consequences

- The star button and its "tornar principal" label are gone from the codebase;
  `promote` the mutation still exists, now invoked by the drag handler instead
  of a click.
- Reordering past the front of the list costs one `PATCH` per affected image, not
  one bulk endpoint — the table's `position` was never given a uniqueness
  constraint, so out-of-order gaps are harmless and no migration was needed.
- An image beyond the two-row fold cannot be dragged or deleted from the summary
  tab directly; reaching it means first dragging something else out of the way.
  Collections large enough for this to bite are rare enough that a dedicated
  "show all" affordance was left for when one actually shows up.
