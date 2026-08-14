# 0012 — LEGO retirement is a date, and it has to arrive

## Context

M9 stored `release_year` and `retired_year` as integers, and `is_retired` was
simply `retired_year IS NOT NULL`.

That makes a set retiring on 31 December 2026 show a «retirado» badge, a tinted
row and an exclusion from `retirement=available` from 1 January 2026 — for the
entire year it is still on the shelves. The one question the field exists to
answer, *can I still buy this?*, is answered wrongly for up to twelve months, and
wrongly in the direction that makes a collector stop looking.

The user offered two ways out: store dates, or keep years and treat a set as
retired only from the following year.

## Decision

Store dates. Both branches of the suggestion collapse into the same rule once the
anchor is chosen.

1. **`release_year` → `release_date`, `retired_year` → `retirement_date`,** both
   `DATE`, both nullable.
2. **`is_retired` = `retirement_date IS NOT NULL AND retirement_date <= today`.**
   An announced future retirement is recorded and shown, but the set is not
   retired until the date arrives.
3. **Year-only sources anchor explicitly and identically everywhere:** a release
   year becomes 1 January, a retirement year becomes **31 December**. The
   migration applies exactly this rule to the existing rows, and the Brickset
   provider applies it to the years it returns. The 31 December anchor is what
   makes the second half of the user's suggestion true: a set known only to retire
   "in 2026" is available for all of 2026.
4. **The grid still reads years.** `LegoSetModelOut` derives `release_year` and
   `retired_year` from the two dates, so the collection table keeps the compact
   «2022 › 2024» column M9.1 asked for. The precision lives in the database and
   in the detail sheet; the summary lives in the table.

A `retirement_precision` flag ("this is the actual date" vs "only the year was
known") was considered and refused: the anchor rule is documented, applied in one
place, and identical on every path in. A column that only ever explains another
column is not worth a migration.

## Consequences

- Every consumer of retirement — the filter, the badge, the row tint, the
  overview's retired-sets count, the workbook export — resolves through the same
  date comparison, so they cannot drift apart.
- The migration is reversible, but the reverse is lossy in the way that matters:
  going back to years reintroduces the bug it fixed.
- `sort=year` now orders by `release_date`, which sorts identically for
  year-anchored rows and better for precise ones.
- A set retiring today is retired today. There is no timezone subtlety worth
  chasing here: this is a shelf, not a settlement.
- The imported household inventory has neither date, because the spreadsheet has
  neither. Those sets answer `retirement=available` and show `—` in the year
  column — absent data, not a guess.
