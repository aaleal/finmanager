# 0050 — A bare number tries the closed pack before the ordinary set

## Context

Brickset keys every set as `<number>-<variant>`, e.g. `10307-1`. Users type the
bare number printed on the box (`10307`), so `normalize_set_number` filled in
the missing `-1` before every Brickset call.

That guess is wrong for a whole family of real sets: collectible packs sold
sealed as one box — the F1 car collectibles are the case that surfaced this —
are keyed `-0` for the closed box, not `-1`. Looking up the bare number always
fetched (or silently failed to fetch) the wrong catalogue entry: wrong name,
wrong image, wrong RRP, all for a set that does exist on Brickset, just under a
number nobody guessed.

Once a pack like this is opened, its contents are no longer one collective
item — each individual car/character *is* a set of its own, with its own
Brickset entry: `10307-1`, `10307-2`, and so on. Nothing about that case was
broken; a user who already knows to type the item's own number gets exactly
that item, because an explicit `-N` suffix was never second-guessed.

## Decision

A bare number (no explicit `-N`) tries `-0` first, then `-1`, and stops at the
first one Brickset actually has (`lego_provider._set_number_candidates` /
`BricksetProvider._set_data`). An explicit suffix is never touched — typing
`10307-2` for an item pulled out of an opened pack looks up exactly that and
nothing else.

Brickset's answer to *which* variant matched — not the bare guess that
triggered the search — is what gets stored and shown everywhere downstream:

1. `LookupResult.set_number` already carried the matched `number` field; it now
   reliably reads `1111-0` for a closed pack instead of whatever the client
   guessed.
2. `add-set-dialog.tsx` replaces the typed «ID do conjunto» with that answer as
   soon as a lookup succeeds — still fully editable afterwards (e.g. to correct
   it to `-2` by hand once the pack is opened and this copy turns out to be a
   different item than first assumed).
3. Bulk import's per-row Brickset lookup (`lego_bulk_import._commit_instance_row`)
   stores the model under the resolved number too, and re-checks for an
   existing model under that resolved number before creating — a second
   spreadsheet row for another copy of the same pack, still typed as the bare
   number, reuses the first row's model instead of racing it into a duplicate
   (`uq_lego_set_models_entity_set_number`) or failing outright.
4. `externalLinks` (constants.ts) stops discarding whatever suffix a
   `set_number` already carries before rebuilding marketplace URLs — it used to
   strip *any* existing `-N` and always re-append `-1`, which would have quietly
   pointed a `-0` pack's links at the wrong item the moment one was stored.

## Consequences

- Registering a closed pack now needs nothing special: type the bare number,
  press «Procurar», and the field itself shows the `-0` it resolved to — that
  is the confirmation that it found the pack, not a random ordinary set that
  happens to share the leading digits.
- Registering what came out of an *opened* pack is unchanged and was never the
  problem: type the item's own number, `-1`/`-2`/…, same as any other set.
  There is no per-instance flag for "this is from an opened pack" — the
  variant number the user types already carries that distinction, and a pack's
  `-0` model and its `-1`/`-2`/… item models are ordinary, independent
  `LegoSetModel` rows with their own instance counts.
- A model registered before this fix under a bare, un-suffixed `set_number`
  (e.g. `"1111"` typed with Brickset disabled, or before this change) is left
  alone — nothing is rewritten in place, matching the standing house rule
  from [ADR-0039](0039-the-sets-own-fields-not-a-shops.md). A fresh «Procurar»
  or bulk-import row is what corrects it going forward.
