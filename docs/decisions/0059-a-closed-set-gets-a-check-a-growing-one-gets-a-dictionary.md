# 0059 — A closed set gets a CHECK, a growing one gets a dictionary

## Context

ADR-0003 settled that enum-ish domains live as `VARCHAR` + `CHECK` rather than a
Postgres enum type, because adding a value is then a one-line migration instead
of a type rewrite. Three new product attributes arrived at once and the rule does
not fit all three the same way:

- **Conservation** — `AMBIENTE`, `REFRIGERADO`, `CONGELADO`. A fourth value would
  be a new physical state of food, not a new word. The set is genuinely closed.
- **Presentation** (the cut) — inteiro, laminado, palitado, ralado, fatiado,
  bife, posta, filete, lombo… This list grows every time the household meets a
  cut it has not bought before.
- **Dietary tags** — Bio, vegan, sem glúten, alto teor proteico… Same, and
  several apply to one product at once.

Putting a CHECK on the cut would make *every new cut a database migration*, which
is the opposite of what ADR-0003 was protecting. Worse, the plan also called for
a shipped JSON vocabulary; a JSON list and a hard-coded CHECK are two copies of
one truth and will drift until an `IntegrityError` reaches a user.

Leaving the cut as unvalidated free text is not an option either — that is how
"Laminada", "laminado" and "lam." become three values and the `GROUP BY` that
ADR-0058 exists for stops working.

## Decision

Split by how the set behaves, not by what layer it lives in.

- `conservation` keeps a CHECK constraint in the schema. Its label is served from
  the dictionary, but the column stores the code and the database enforces it.
- `presentation` and `dietary_attributes` have **no CHECK**. They are enforced in
  the service layer against
  `apps/api/app/data/supermarket-product-attributes.pt-PT.json`, read by
  `app.services.supermarket.attributes`. A value outside the dictionary is
  refused with the accepted values in the message; adding one is an edit to that
  file and no migration.

Every spelling funnels through `normalize_description`, the same accent-, case-
and punctuation-blind key the catalogue already matches on, so «Sem Glúten»,
«sem gluten» and «S/ GLUTEN» arrive as one value. Synonyms are declared in the
JSON beside the canonical label, which is what lets a spreadsheet column say
"laminada" and land on `Laminado`.

The vocabulary is **served**, not duplicated in the client:
`GET /api/master-products/attributes` — registered above `/{product_id}`, per the
routing-collision note in ADR-0055.

## Consequences

- Adding a cut or a dietary tag is a one-line JSON edit deployed with the
  release. Adding a conservation state is a JSON edit *and* a migration, and that
  asymmetry is the point.
- The dictionary can be tightened into a CHECK later; a CHECK could not have been
  loosened without one.
- **An unfilled attribute is not an error.** The overwhelming majority of the
  ~1.5k products already in the catalogue carry none of these values, and the
  source spreadsheet only mentions a cut in 5,3 % of its distinct descriptions
  and a conservation state in 0,5 %. There is nothing to derive them from, so
  they are nullable, never required, and report as "por indicar" — the same
  contract ADR-0035 gives an unconfirmed category, for the same reason.
- Dietary spend gets its own endpoint rather than a dimension of
  `category_spend`: tags overlap, so their rows do not partition spend and a
  Bio *and* vegan product is counted under both. Folding that into a view whose
  other axes do partition would make the difference invisible.
