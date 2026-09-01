# 0033 — A line's confidence is scored again after the catalogue answers

## Context

`item_confidence()` combines two signals: the quality of the text the line was
read from, and the strength of the product match. The pipeline, however, builds
its rows **before** the catalogue stage runs, so it had no match to give and
passed `product_match=None` — meaning "the stage did not run", which the engine
correctly handles by scoring on text alone (ADR-0018).

The catalogue stage then ran, set `master_product_id`, appended its own reasons
— and left the score untouched. A line matched at 0,95 and a line matched to
nothing therefore carried the **same** confidence, and the review grid had no
way to tell the reader which of the two problems it was looking at.

## Decision

`_resolve_products()` re-scores every line once it has resolved it, replacing
the provisional `ocr_text`-only reasons with the full pair. The text signal is
read back from the reason the first pass recorded, so nothing has to be threaded
through the pipeline to make it available twice.

The review grid shows the two signals side by side — `98 % / 0 %` — rather than
their average.

## Consequences

- An unresolved line now scores visibly lower, which is what pushes it up the
  review queue instead of letting it pass as merely "read well".
- The two numbers separate two different jobs: a blurry line needs the document
  re-read, an unmatched line needs a product picked. One average hid which.
- `decision_reasons` gains no rows: the provisional `ocr_text` reason is
  replaced, not appended to, so the explanation never contradicts itself.
- Nothing here changes the **receipt**-level score, which already consumed the
  average match across lines as its `product_match` signal.
