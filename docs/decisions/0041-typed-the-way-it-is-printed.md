# 0041 — Typed the way it is printed

## Context

Three fields on the LEGO set form were asking the user to translate something
they can read directly off the box.

1. **Dates.** `<input type="date">` renders in the *browser's* locale, not the
   document's. On a Chrome installed in English — the common case on this
   household's machines — a pt-PT application asks for `mm/dd/yyyy`. There is no
   attribute, `lang` included, that changes it: the format is the browser's to
   pick.
2. **The age.** The box prints one number: `18+`, or `4+`, or occasionally
   `6-12`. Brickset models it as `{min, max}` and the form mirrored that with two
   inputs, one of which is empty almost always.
3. **The box size.** Same story: three numeric inputs for a figure that is
   written on the packaging, and quoted everywhere else, as a single string.

## Decision

Each of the three is one field, in the notation the box uses.

1. A `DateInput` component: a text field masked to `dd/mm/aaaa`, holding an ISO
   `yyyy-mm-dd` value for the API. The native date input survives underneath the
   calendar icon, so the picker still opens — the format is ours, the widget is
   still the platform's. It replaced every `type="date"` in the application, not
   only the LEGO ones: a date reads the same way on every screen or the rule is
   not a rule.
2. One «Idade recomendada» field, parsing `18+`, `+18`, `18` and `6-12`.
3. One «Dimensões da caixa» field, parsing `26,2 × 7,1 × 38,2` — `x`, `×` and
   `*` all separate, and both decimal marks are accepted.

The database keeps `age_min`/`age_max` and the three `box_*_cm` columns. They are
separate facts, they sort and filter separately, and a text column would have to
be re-parsed by every future reader. The single field is a **presentation**, and
the parsing lives beside the labels in `features/lego/constants.ts`, tested there.

## Consequences

- A half-typed date (`03/09/`) emits nothing: the field holds its own draft and
  only reports upwards once the ten characters parse. Clearing it reports `''`,
  which is how a date is removed.
- The parsers are permissive on input and canonical on output, so pasting
  `26.2x7.1x38.2` from a listing works and re-renders as `26,2 × 7,1 × 38,2`.
- Text that parses to nothing (`a partir dos 8`) clears the field rather than
  refusing the save. The value is a convenience, not a fact the collection
  depends on.
