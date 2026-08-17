# 0016 — Per-merchant parsers over one configurable parser

## Context

The eleven fixtures under `apps/api/tests/fixtures/receipts/` were transcribed and
compared line by line. The differences between merchants are **positional and
semantic, not cosmetic**:

| Merchant | IVA class token | Line value | Invoice-level arithmetic |
|---|---|---|---|
| Continente | first, in parens `(C)` | already **net** of POUPANCA | `SUBTOTAL − Desconto Cartão = TOTAL` |
| Pingo Doce | first, bare | **gross** | `TOTAL − POUPANÇA = TOTAL A PAGAR` |
| Lidl | **last** | gross, no discounts observed | — |
| Piquete | quantity printed first; IVA as a literal `6%` | gross | — |

A single configurable parser would have to carry a field for "does the line
value already net out the card discount" and flip it per merchant — at which
point it is not one parser, it is four parsers wearing a shared `if`.

## Decision

One parser class per merchant (`continente_v1`, `pingodoce_v1`, `lidl_v1`,
`piquete_v1`) plus one generic fallback (`generic_v1`), selected by a
`MerchantParserProfile` whose `detection_patterns` are matched **before** field
extraction (`pipeline.select_profile`). `field_hints` tunes a parser — a changed
regex, a relabelled column — without a deploy, but it cannot replace one: there
is no hint that turns `pingodoce_v1` into `lidl_v1`.

The generic profile is unique (`uq_merchant_parser_profiles_generic`, a partial
index on `merchant_id IS NULL`) and undeletable, so an unrecognised merchant is
never a dead end.

## Consequences

- A single parser tuned for one merchant's semantics would silently overstate
  or understate the other's spending the moment it was adjusted — Continente's
  net line value and Pingo Doce's gross one cannot both be "the line value" in
  the same code path without a household finding out the hard way.
- An unknown merchant still parses, generically, and lands on
  `NEEDS_REVIEW` rather than failing outright.
- `success_rate` on `MerchantParserProfile` is **observed**, not configured — it
  is written by the pipeline, shown in the parser-profile administration
  screen, and is never hand-set to make a merchant look solved.
