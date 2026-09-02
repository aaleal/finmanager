# 0039 — The set's own fields, not a shop's

## Context

The Brickset lookup filled `retirement_date` from
`LEGOCom.DE.dateLastAvailable`, falling back to `UK` and then `US`, and
`release_date` from the set's `year` anchored to the 1st of January.

Both are the wrong readings, and the retirement one is visibly wrong. Brickset's
`sets` class carries `launchDate` and `exitDate` — the dates the *set* was on and
off the market — alongside a `LEGOCom` block that is a **per-store** record: when
each national LEGO.com shop first and last listed it. For 10280-1 the difference
is not academic:

| Field | Value |
|---|---|
| `exitDate` | 2026-07-31 |
| `LEGOCom.DE.dateLastAvailable` | 2026-07-03 |
| `LEGOCom.UK.dateLastAvailable` | 2026-06-29 |

The old code showed the German shop's last day and called it retirement. Worse,
the `DE → UK → US` fallback chain also chose the *price*: a set the German store
never sold imported a pound or dollar figure straight into `rrp_eur`, a
`NUMERIC(10,2)` column the whole application reads as euros.

## Decision

Read the set's fields for the set's facts, and a store's fields only for that
store's price.

1. `retirement_date` comes from `exitDate`. When Brickset has none, the fallback
   is the **latest** `dateLastAvailable` across every region — the last day any
   shop still had it is the best available evidence that it is gone — never the
   first region that happens to have the key.
2. `release_date` comes from `launchDate`, with the old 1st-of-January anchor
   kept only for the older sets that have a `year` and nothing else.
3. `rrp_eur` comes from `LEGOCom.DE` and from nowhere else. Germany is the only
   euro store in the block. A set with no German price now arrives with no RRP,
   which is true, instead of a foreign number that reads as euros.

## Consequences

- A set looked up before this fix keeps whatever it was given; nothing is
  rewritten in place. Pressing «Procurar» again on a new set is what corrects it,
  and both dates stay editable by hand ([ADR-0012](0012-lego-retirement-is-a-date.md)
  already made retirement a date the user owns).
- The RRP ROI ([ADR-0010](0010-lego-cost-roi-and-rrp-roi.md)) is now missing for
  a handful of never-sold-in-Germany sets rather than silently wrong for them.
  A missing reading is a state the UI already renders; a wrong one is not.
- `ageRange` and `dimensions` were read from the same payload in the same pass,
  for the same reason: they are the set's own fields and were already there.
