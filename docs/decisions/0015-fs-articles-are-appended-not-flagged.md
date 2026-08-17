# 0015 — An Fs article is appended, never a printed line reclassified

## Context

The household calls freebies and gifts "Fs". An earlier reading of the domain
treated it as a flag on a printed line, with its own `fs_total` sitting alongside
the line's real values. The 2025 spreadsheet shows why that reading is wrong: 425
rows (17.5 %) are Fs, and its `Preço Fatura` column already **excludes** their
value — an Fs row was never part of what the invoice charged, so there is no
printed line to flag in the first place.

## Decision

An Fs article is a row the user **appends**; it was never on the invoice.

- `paid_price_eur` is always `0.00` — no money moved.
- The notional worth lives in `unit_price_pvp_eur` and is `pvp × quantity`
  (`arithmetic.notional_value_eur`).
- `line_no`, `merchant_section` and `iva_class_raw` are all `NULL`, and a `CHECK`
  constraint (`fs_has_no_document_fields`) enforces it at the database level:
  nothing the *document* would have supplied can exist on a row the document
  never had.

Derived, never stored: `notional_total_eur = total_eur + fs_value_eur` and
`fs_share_pct = fs_value / total × 100` — so €10 of Fs on a €10 invoice is 100 %,
not 50 %.

## Consequences

- Appending an Fs article cannot disturb a reconciliation that already passed —
  `total_eur`, `computed_total_eur` and `is_reconciled` stay byte-identical
  before and after, checked by `fs_pays_nothing`. It is therefore legal to add
  one even on a `CONFIRMED` receipt, and
  `tests/unit/test_receipt_fs_split.py` asserts exactly that.
- The deliberate asymmetry is worth stating plainly rather than discovering by
  accident: on a parsed line, `unit_price_pvp_eur` is the *line* gross — what
  `pvp − promo − allocated` needs to reconcile. On an Fs line, the same column
  is the value of *one* article, because there is no promo and no allocation to
  net it against.
- `F` and `FS` must never be pattern-matched as the household's flag. Lidl prints
  `F` as its 0 % IVA class letter (`Deposito 0.10 0,10 F`), and every merchant
  numbers its documents `FS 013700526/091423` for *fatura simplificada*. Neither
  has anything to do with a hand-appended freebie, which is never printed and
  never parsed.
