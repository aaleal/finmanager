# Module 1 — Supermarket & Receipt Processing

## 1. Purpose and Scope
Ingest supermarket invoices (PDF, photo or manual entry), identify and normalize
every product, categorize it into the 3-tier pt-PT taxonomy, track consumption
and price evolution, and automate duplicate detection and shrinkflation alerts —
so the household knows what it actually spends on groceries without typing it
in.

This is the **crown-jewel ingestion module**. The receipt review screen is the
flow the entire automation-first thesis is judged on: data arrives messy, the
system parses, matches and scores it, **auto-accepts what it is confident
about**, and routes only the uncertain remainder to the shared Review Queue. The
target is **≥80% of receipts auto-accepted with zero user edits** on the seed
sample.

Unlike M9, this module cannot be flat. It carries eight tables because each
answers a question a field cannot: what the invoice claimed (`Receipt`) versus
what the items sum to (`ReceiptItem`), what a product *is* (`MasterProduct`)
versus what a merchant *calls* it (`ProductAlias`), how a given merchant's
layout is parsed (`MerchantParserProfile`), and an immutable price observation
(`ProductPriceHistory`) that must survive a later correction to its source
receipt. Everything beyond that is deliberately a field, not a table.

**Processing is local by default.** Parsing, OCR, normalization, matching and
scoring each have a local engine that works with no subscription and no network,
and those are what ship enabled. A remote engine is a supported *option*, not a
forbidden one: every stage sits behind a provider seam and a remote
implementation can be registered and switched on per stage once a subscription
exists. Nothing degrades while it stays off — see Decision #13.

All monetary fields are EUR only. Scope is supermarket and grocery retail; other
receipt types must not influence the initial domain model.

**Dependencies.** Every shared entity this module touches — `Entity`,
`Merchant`, `Category`, `Tag`, `Document`, `Link`, `ReviewTask`, `Setting`,
`AuditLog`, `ImportBatch`, `ProcessingJob` — is defined once in the orchestrator
brief §1a and is **consumed, never redefined here**. If one does not exist yet
when this module is built, it is created by whichever phase owns it, to the §1a
definition. The full list is in the Integration Contract at the end of this
file. This module assumes nothing about build order.

---

## Actors

### Primary Actor
A member of the household who buys groceries and wants that spending tracked
accurately without typing it in. The same person photographs the receipt,
resolves whatever the system flagged, corrects a mis-matched product, and later
looks at what a kilo of coffee now costs. There is **one human actor wearing
several hats at different moments** — shopper, reviewer, price analyst,
catalogue maintainer — not several actors: they carry identical permissions,
share one workspace, and no workflow branches on which hat is being worn.

Read/write power is governed solely by the M7 role (`OWNER`/`MEMBER` write,
`VIEWER` reads); that is a cross-cutting concern of the household module and is
not re-specified here. Dependents (children) never act — they are only ever the
*subject* of an attributed record.

### Supporting Actor
This module is automation-first, so one non-human actor does most of the work:

- **The ingestion pipeline** — selects a parser, extracts, normalizes, matches, classifies, scores confidence and proposes reconciliation links, unattended, inside a Celery `ProcessingJob`. It is the actor in most user stories below; the human confirms rather than types. Every stage runs on a local engine unless a remote one has been explicitly configured.

---

## User Stories

### US01. Effortless Capture
As a user, I want to photograph or drop in a receipt and have the merchant,
date, line items, weights, prices and discounts extracted for me, so I never
retype an invoice.

### US02. Review Only the Uncertain
As a user, I want to see only the fields the system was unsure about — flagged
clearly and side by side with the original image — so I can confirm a whole
receipt in seconds instead of checking every line.

### US03. Explainable Decisions
As a user, I want to ask "porquê?" of any value the system filled in and see the
reasons and scores behind it, so I can trust it or correct it on an informed
basis.

### US04. Corrections That Stick
As a user, I want a product I re-matched by hand to be remembered for that
merchant, so the same description resolves itself next time and the system gets
better the more I use it. When I type a product name I want autocomplete over
what I already own, so I never create a near-duplicate by accident.

### US05. Meaningful Categorization
As a user, I want every item placed in the household's own pt-PT category tree,
auto-suggested and always overridable through an autocomplete picker, so my
spending analysis matches how I actually think about groceries.

### US06. The Fs Split
As a user, I want to add to a receipt the articles that were not on it — tagging
them Fs and recording what each was worth — so I can see what the shop actually
cost me, what it would have cost had I paid for everything, and filter any view
to Fs articles, non-Fs articles, or all of them.

### US07. Price per Kilo Over Time
As a user, I want to see how the price per kilo of a product has moved across
merchants and seasons, in list price and in what I actually paid, so I know when
something genuinely got more expensive.

### US08. Shrinkflation Alerts
As a user, I want to be told when a product I buy regularly got lighter while
the price held or rose, so I notice the increase the packaging is hiding.

### US09. Never Count a Receipt Twice
As a user, I want the system to spot a receipt I already uploaded and ask before
merging, so a double upload never inflates my spending.

### US10. Loyalty Savings
As a user, I want the cartão discount tracked and spread correctly across the
items it applied to, kept apart from per-item promotions, so I can see what
loyalty actually saves me.

### US11. Dietary and Allergen Visibility
As a user, I want to filter what I bought by dietary attributes and allergens,
so I can monitor specialized spending and avoid what we cannot eat.

### US12. Tie a Receipt to the Bank
As a user, I want a receipt matched to the statement line that paid for it —
automatically when it is obvious, by picker when it is not — so my groceries
reconcile against my account.

### US13. Bring the Spreadsheet Across
As a user, I want my years of `SUPERMERCADOS_YYYY` rows imported without
duplication and re-runnable if it goes wrong, so I keep my history.

### US14. Queue a Pile of Invoices
As a user, I want to drop several invoices at once into a parsing queue and walk
away, then come back to see which parsed cleanly, which need me and which failed
— and retry the failures without re-uploading.

### US15. Parsers That Know the Merchant
As a user, I want Continente receipts read by a parser built for Continente's
layout and Pingo Doce's by its own, falling back to a generic parser for
anything unrecognised, so accuracy improves per merchant instead of one brittle
parser serving all.

### US16. Works Without a Subscription
As a user, I want the whole pipeline to work on my own NAS with no paid service
attached, and to be able to plug a better engine in later without rebuilding
anything, so I am never blocked today and never boxed in tomorrow.

### US17. Two Levels of Detail
As a user, I want to browse either one row per invoice or one row per purchased
article across every invoice, and from any article jump straight to the original
invoice image, so I can answer both "what did I spend in March" and "every time
I ever bought this coffee".

### US18. Confirmed Classifications
As a user, I want to see which categories the system guessed and which I have
actually confirmed, so I can work through the unconfirmed ones and trust the
rest.

### US19. My Own Category Tree
As a user, I want to rename, move, merge and retire categories as my thinking
changes, and understand what that does to the data I already have, so the
taxonomy stays mine rather than something I inherited once and can never fix.

---

## Data Model

### Entities & Attributes

All monetary attributes are EUR only (no multi-currency, no FX). Stored as
`NUMERIC(10,2)` decimal EUR (e.g. `19.99`); the UI displays them pt-PT-formatted
(e.g. `19,99 €`) through the shared money util only.

Every row carries `entity_id` — the owning household entity. Entity is an
**attribution and filter** dimension, not a security boundary: every household
member can read every entity's receipts (see M7).

**Definition — the Fs split.** Everything the invoice prints is a normal paid
item. An **Fs item is an article that was never on the invoice at all** and that
the household **adds by hand afterwards**, attached to that receipt. It is
classified exactly like a paid product — master product, category, quantity,
unit, weight — and carries a **notional value**: what it would have cost had it
been bought. `ReceiptItem.is_fs` marks it, and it is never parsed, because there
is nothing on the document to parse (Decision #31).

Worked example — an invoice of 10 paid articles totalling €10, to which the user
adds 2 Fs articles worth €5 each:

| Figure | Value | Meaning |
| :--- | :--- | :--- |
| `total_eur` | `10.00` | What the invoice printed and the household paid |
| `fs_value_eur` | `10.00` | Value of the 2 added Fs articles |
| `notional_total_eur` | `20.00` | Hypothetical cost had everything been paid for |
| `fs_share_pct` | `100 %` | Fs value against what was actually paid |

The arithmetic follows from one rule: **an Fs item carries
`paid_price_eur = 0.00`, because no money moved.** Its value lives in
`unit_price_pvp_eur`. Adding one therefore cannot disturb a single printed
figure or a reconciliation that already passed:

| Measure | Definition | Answers |
| :--- | :--- | :--- |
| `paid_price_eur` | What left the household's pocket | "What did I spend?" |
| `notional_value_eur` | `is_fs ? unit_price_pvp_eur × quantity : paid_price_eur` | "What was this worth?" |

**Fs articles are excluded from everything that describes the document, and
included in everything that describes consumption.** They have no `line_no`, no
`merchant_section` and no `iva_class_code` — the invoice never mentioned them —
so the printed `item_count` is compared against non-Fs rows only and **never
moves when an Fs article is added**; `fs_item_count` counts them separately. But
they are real products the household consumed, so quantity, cost and price
history all include them, governed by the `fs` filter that every query and
screen must offer: `only` \| `exclude` \| `all` (default `all`).

The notional value comes from the product's last observed price in
`ProductPriceHistory` when it is known, otherwise typed in by the user.
`notional_value_source` records which — not to distrust the figure, but so the
filter has something to act on.

> **An Fs value is taken at face value.** It enters `ProductPriceHistory` as a
> normal observation and participates in €/kg trends and shrinkflation like any
> other, because the household's estimate is treated as correct. What makes this
> safe is not exclusion but **visibility**: `is_fs` travels onto the snapshot, so
> any price analysis can be run with Fs, without Fs, or over both.
>
> On an Fs snapshot **both** `list_price_eur` and `paid_price_eur` carry the
> notional value — not `0.00`. The receipt item records what was *spent* (zero);
> the price history records what the product was *worth*. Writing `0.00` here
> would drag every paid-price trend for that product towards zero.

**Definition — `is_fs` is not a `product_flag`.** Every `product_flag` value is
read off the document; an Fs item **has no document origin whatsoever**. Keeping
`F` inside that enum conflated "what the receipt said" with "what the household
added afterwards", which is the one distinction this whole section exists to
draw.

**Definition — neither is a tag.** These are unrelated mechanisms and conflating
them breaks the arithmetic:

| | `is_fs` / `product_flag` | `tags[]` |
| :--- | :--- | :--- |
| What it is | A **structural** property of the line | A **cross-cutting label** the household applies |
| Vocabulary | Boolean / closed enum (`REFUND`, `DEPOSIT_RETURN`, `SEASONAL`, `OTHER`) | Open, user-created (`#férias`, `#culinária`, `#social`) |
| How many | One boolean, plus one enum value or none | Any number |
| Effect on money | **Decides how the item is valued** | **None whatsoever** |

The household's own taxonomy file makes the same distinction: its
`context_flags` are described as *"flags de contexto … distintas da flag de
exclusão Fs"*. So `#férias` is a tag; `Fs` never is.

**Definition — claimed versus computed.** `Receipt.total_eur`,
`total_discount_eur` and `item_count` are **what the invoice printed** —
independent facts extracted from the document. The item rows are what we parsed.
Reconciliation is the comparison of the two, and it is a *confidence signal*,
never a silent correction of either side. Everything Fs-related is **computed
from the rows**, never claimed, because nothing about it is printed.

---

#### 1. `Receipt` (One Payment Transaction at One Merchant)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `entity_id` | `UUID` | Owning entity (attribution/filter) |
| `merchant_id` | `UUID` | FK → Core `Merchant`; must already exist |
| `purchased_at` | `Timestamp` | Instant of purchase, stored UTC |
| `purchase_date` | `Date` | Local `Europe/Lisbon` calendar date — **never UTC-shifted** |
| `document_id` | `UUID` | FK → Core `Document` (the original PDF/image) |
| `parser_profile_id` | `UUID?` | FK → `MerchantParserProfile` actually used; `NULL` when parsed generically |
| `import_batch_id` | `UUID?` | FK → Core `ImportBatch` when bulk-imported |
| `processing_job_id` | `UUID?` | FK → Core `ProcessingJob` for the parse run |
| `total_eur` | `NUMERIC(10,2)` | Printed invoice total actually paid |
| `total_discount_eur` | `NUMERIC(10,2)` | Printed total discount; drives the proration ratio |
| `item_count` | `Integer` | Printed article count; cross-checked against non-Fs rows only |
| `status` | `Enum` | See the lifecycle below |
| `confidence` | `NUMERIC(4,3)?` | Combined score, 0–1 |
| `decision_reasons` | `JSONB` | `[{rule, detail, score}]` — rendered behind "Porquê?" |
| `raw_ocr_payload` | `JSONB?` | Provider output; **never selected in list queries** |
| `atcud_code` | `String?` | Portuguese tax stamp read from the QR code |
| `atcud_valid` | `Boolean?` | Structural validation result |
| `atcud_reason` | `String?` | Why validation failed, when it did |
| `parsed_payment_methods` | `JSONB` | `[{method, amount_eur}]` for composite payments |
| `tags` | `UUID[]` | Core `Tag` ids |
| `notes` | `Text?` | Free-text notes |
| `void_reason` | `Text?` | Mandatory when `status = VOID` |
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `created_at` / `updated_at` / `deleted_at?` | `Timestamp` | Audit timestamps |

**Status lifecycle** — a guarded state machine; illegal transitions are rejected
and every change writes an `AuditLog` row:

```
UPLOADED ──▶ PARSING ──┬──▶ AUTO_ACCEPTED ──▶ CONFIRMED ──▶ VOID
                       ├──▶ NEEDS_REVIEW ───▶ CONFIRMED ──▶ VOID
                       └──▶ FAILED ────────▶ PARSING (retry)
```

**Constraints & Rules:**
- `AUTO_ACCEPTED` is reached with no human input when `confidence ≥ confidence.auto_accept`. **This is the state the ≥80% rubric measures.**
- `NEEDS_REVIEW` creates exactly one `ReviewTask` (`module = "receipts"`, `subject_type = "Receipt"`).
- `VOID` replaces deletion once a receipt is confirmed; `void_reason` is required.
- Re-uploading a file whose SHA-256 already exists for this entity never creates a second receipt.
- Unique on `(entity_id, document_id)`.

---

#### 2. `ReceiptItem` (One Purchased Article)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `receipt_id` | `UUID` | FK → `Receipt` |
| `entity_id` | `UUID` | Denormalized from the parent (see Decision #8) |
| `line_no` | `Integer?` | Position on the invoice; **`NULL` for an Fs item**, which was never printed |
| `merchant_section` | `String?` | The merchant's own heading above this line (`"Mercearia Salgada"`, `"FRUTAS E VEGETAIS"`) — a no-cost classification signal |
| `description_raw` | `String` | Text exactly as printed; for an Fs item, what the user typed |
| `description_norm` | `String` | Accent/case/unit-stripped form used for matching — **the only key a receipt line gives us** |
| `master_product_id` | `UUID?` | FK → `MasterProduct`; `NULL` until resolved |
| `category_l3_id` | `UUID?` | **Deepest assigned category — authoritative** (see Category Governance) |
| `category_l1_id` / `_l2_id` | `UUID?` | Maintained denormalization of the ancestors, refreshed on reparent |
| `category_status` | `Enum` | `AUTO` \| `VALIDATED` \| `MANUAL` (`default: AUTO`) |
| `category_confidence` | `NUMERIC(4,3)?` | Score behind an `AUTO` assignment |
| `quantity` | `NUMERIC(14,4)` | As printed; negative for refunds |
| `unit` | `Enum` | `KG` \| `G` \| `L` \| `ML` \| `UN` \| `PACK` |
| `quantity_canonical` | `NUMERIC(14,4)` | Normalized quantity |
| `unit_canonical` | `Enum` | `KG` \| `L` \| `UN` — families never convert between each other |
| `weight_listed_kg` | `NUMERIC(14,4)?` | Label weight, proposed from the matching `MasterProduct.pack_variants` entry |
| `weight_observed_kg` | `NUMERIC(14,4)?` | Real weight from the register scale |
| `is_bulk_weighed` | `Boolean` | Priced at the checkout scale (`default: false`) |
| `unit_price_pvp_eur` | `NUMERIC(10,2)` | List/gross price before any discount; on an Fs item, its **notional value** |
| `promo_discount_eur` | `NUMERIC(10,2)` | Per-item promotion only (`default: 0.00`) |
| `promo_type` | `Enum?` | `ABSOLUTE` \| `PERCENTAGE` \| `BOGO` \| `LOYALTY_POINTS` |
| `invoice_allocated_discount_eur` | `NUMERIC(10,2)` | Invoice/loyalty discount **prorated** onto this item |
| `paid_price_eur` | `NUMERIC(10,2)` | Net spend after all discounts; **always `0.00` on an Fs item** |
| `iva_class_code` | `String(2)?` | The class letter **as printed** (`A`, `C`, `E`, `I`); `NULL` for an Fs item |
| `iva_rate` | `Enum` | `0` \| `6` \| `13` \| `23` — resolved from `iva_class_code` via the merchant's map |
| `iva_inferred` | `Boolean` | `true` only when no class letter was printed |
| `is_fs` | `Boolean` | **Fs item** — added by hand, never on the invoice (`default: false`) |
| `notional_value_source` | `Enum?` | `PRICE_HISTORY` \| `MANUAL` — where an Fs item's value came from |
| `product_flag` | `Enum?` | `REFUND` \| `DEPOSIT_RETURN` \| `SEASONAL` \| `OTHER` — all read off the document |
| `dietary_tags` | `JSONB` | `ORGANIC` \| `VEGAN` \| `GLUTEN_FREE` \| … |
| `allergen_flags` | `JSONB` | Allergens carried from the master product |
| `is_duplicate_of_item_id` | `UUID?` | Set when a duplicate receipt was merged |
| `tags` | `UUID[]` | Core `Tag` ids |
| `notes` | `Text?` | Free-text notes (legacy `Notas`) |
| `legacy_row_ref` | `Integer?` | Spreadsheet row id, traceability only — **not** the PK |
| `confidence` | `NUMERIC(4,3)?` | Per-item score |
| `decision_reasons` | `JSONB` | Per-item reasons |
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `created_at` / `updated_at` | `Timestamp` | Audit timestamps |

**Price arithmetic — three distinct quantities that must never be collapsed:**

| Field | Formula | Legacy column |
| :--- | :--- | :--- |
| `unit_price_pvp_eur` | source | `Price` |
| `promo_discount_eur` | source | `PromoInd` |
| `invoice_allocated_discount_eur` | `(pvp − promo) × invoice_discount_ratio` | `PromoGlob` |
| `paid_price_eur` | `pvp − promo − invoice_allocated` | `Price_Final` |

**Constraints & Rules:**
- The most common bug in this domain is summing per-item promos and missing the invoice-level credit. Only `pvp − promo − invoice_allocated` reconciles.
- **Three names, three jobs.** `description_raw` is verbatim and never modified — it is the audit trail against the paper. `description_norm` is a matching key and is **never displayed**. The name shown to the user is `MasterProduct.canonical_name` once resolved, falling back to `description_raw` while unresolved.
- `category_status` starts at `AUTO`, becomes `VALIDATED` when a human confirms the suggestion, and `MANUAL` when a human assigns the category directly. `MANUAL` counts as validated for every filter and KPI.
- `iva_eur` is **not stored** — it is derived (see Computed & Derived Fields).
- Refunds carry `quantity < 0` and are excluded from the paid total; the refund count is derived, not stored.
- Deposits (*tara*) use `product_flag = DEPOSIT_RETURN` and are never categorized as groceries.

---

#### 3. `MasterProduct` (Canonical Product Identity, User-Managed)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `canonical_name` | `String` | Household's name for the product; **the name shown everywhere** |
| `brand` | `String?` | Brand; lives here, never in the category tree |
| `pack_variants` | `JSONB` | `[{label?, weight_kg?, barcode?}]` — every pack size this product ships in |
| `default_category_l3_id` | `UUID` | Deepest suggested category |
| `default_category_l1_id` / `_l2_id` | `UUID` | Maintained ancestors |
| `dietary_attributes` | `JSONB` | `ORGANIC` \| `VEGAN` \| `GLUTEN_FREE` \| … |
| `allergen_list` | `JSONB` | Allergens |
| `seasonal_flags` | `JSONB` | `SPRING` \| `SUMMER` \| `AUTUMN` \| `WINTER` |
| `expected_shelf_life_days` | `Integer?` | Stored now; alerting deferred |
| `deposit_value_eur` | `NUMERIC(10,2)?` | Bottle/packaging deposit |
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `created_at` / `updated_at` | `Timestamp` | Audit timestamps |

**Immutable rule: two items with different categories are, by rule, different
master products.** L3 is the normalized product-*genus*; brand, variant and
package live here.

**One product, many pack sizes (Decision #15).** A 500 g and a 1 kg bag of the
same coffee are **one** `MasterProduct` — that is what makes €/kg comparable
across them. What differs between them is the **weight**, and `pack_variants` is
what lets one product carry several:

```json
[{"label": "500 g", "weight_kg": 0.500},
 {"label": "1 kg",  "weight_kg": 1.000}]
```

Receipts embed the size in the description itself (`POLPA TOMATE GULOSO 500G`,
`SAL GROSSO CONTINENTE 1KG`), so the variant is matched by parsing that text
against these weights — there is no code to join on. `barcode` remains an
accepted optional key on a variant for the deferred scan-to-find flow, but
**nothing in the ingestion pipeline reads it** — see Decision #23. This single
field replaces what were three (`barcode`, `sku_reference`, `curated_weights`)
and one that never earned its keep (`curated_isoweight_equivalents`).

---

#### 4. `ProductAlias` (Learned Merchant Vocabulary)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `master_product_id` | `UUID` | FK → `MasterProduct` |
| `merchant_id` | `UUID` | FK → Core `Merchant` |
| `merchant_description` | `String` | Raw text as that merchant prints it |
| `description_norm` | `String` | Normalized form actually matched against |
| `confidence` | `NUMERIC(4,3)` | Learned trust, rises with corrections |
| `correction_count` | `Integer` | How many times a human confirmed this mapping |
| `last_used_at` | `Timestamp?` | Last successful match |
| `created_at` / `updated_at` | `Timestamp` | Audit timestamps |

Unique constraint: `(merchant_id, description_norm)`. Aliases are a table rather
than a JSON blob on the product precisely because they are **learned** and carry
per-merchant confidence.

---

#### 5. `ProductPriceHistory` (Immutable Price Observation)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `master_product_id` | `UUID` | FK → `MasterProduct` |
| `merchant_id` | `UUID` | FK → Core `Merchant` |
| `observed_on` | `Date` | Purchase date of the source receipt |
| `is_fs` | `Boolean` | Snapshot of the source item's Fs status, so price analysis can filter without a join (`default: false`) |
| `weight_kg` | `NUMERIC(14,4)?` | Weight used for the €/kg figures |
| `list_price_eur` | `NUMERIC(10,2)` | Snapshot of the list price; the notional value on an Fs row |
| `paid_price_eur` | `NUMERIC(10,2)` | Snapshot of what was paid; **also the notional value on an Fs row**, never `0.00` |
| `price_per_kg_pvp_eur` | `NUMERIC(10,2)?` | Snapshot, list price per kg |
| `price_per_kg_paid_eur` | `NUMERIC(10,2)?` | Snapshot, paid price per kg |
| `shrinkflation_indicator` | `Boolean` | Weight fell while price held or rose |
| `source_receipt_item_id` | `UUID` | Provenance |
| `created_at` | `Timestamp` | Audit timestamp |

**Append-only and immutable.** This is the one place €/kg is *persisted*,
because it is a historical snapshot: correcting a receipt item later writes a
**new** row and never rewrites the past.

---

#### 6. `ReceiptDuplicateLog` (Suspected Duplicate Pair)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `original_receipt_id` | `UUID` | The receipt already held |
| `potential_dup_receipt_id` | `UUID` | The suspect |
| `detection_method` | `Enum` | `HASH` \| `MERCHANT_DATE_AMOUNT` \| `OCR_SIMILARITY` |
| `similarity_score` | `NUMERIC(4,3)` | 0–1 |
| `status` | `Enum` | `PENDING` \| `CONFIRMED` \| `DISMISSED` |
| `review_task_id` | `UUID?` | The `ReviewTask` raised for it |
| `reviewed_at` / `reviewed_by` | `Timestamp?` / `UUID?` | Resolution audit |
| `created_at` | `Timestamp` | Audit timestamp |

Unique constraint: `(original_receipt_id, potential_dup_receipt_id)`.

---

#### 7. `LoyaltyAllocation` (How a Cartão Discount Was Spread)

One row per receipt that carried a loyalty discount. There is no separate
`LoyaltyCard` table (see Decision #4): the merchant already prints the card
number pre-masked on the till receipt, so nothing sensitive ever needs
encrypting, and a household's two or three cards do not earn a management screen
of their own.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `receipt_id` | `UUID` | FK → `Receipt` |
| `scheme_name` | `String` | e.g. `"Cartão Continente"`, `"Poupa Mais"` |
| `card_number_masked` | `String?` | Exactly as printed on the receipt (e.g. `"XXXXXXXX3394X"`) — never a full number |
| `accrued_eur` | `NUMERIC(10,2)` | Value credited to the card by this purchase (`ACUMULOU NO SEU CARTAO`) |
| `discount_applied_eur` | `NUMERIC(10,2)` | Card balance spent on this receipt (`Desconto Cartao Utilizado`) |
| `allocation_method` | `Enum` | `PROPORTIONAL` \| `ITEM_LEVEL` |
| `applied_to_item_ids` | `UUID[]` | Items that received a share |
| `created_at` | `Timestamp` | Audit timestamp |

---

#### 8. `MerchantParserProfile` (How One Merchant's Layout Is Read)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `merchant_id` | `UUID?` | FK → Core `Merchant`; **`NULL` = the generic fallback profile** |
| `name` | `String` | e.g. `"Continente talão térmico"` |
| `parser_key` | `String` | Registered parser implementation, e.g. `continente_v1` |
| `document_kinds` | `JSONB` | Which inputs it handles: `PDF_DIGITAL` \| `IMAGE_SCAN` |
| `detection_patterns` | `JSONB` | Regexes / anchor strings that identify this merchant's layout |
| `field_hints` | `JSONB` | Layout hints — at minimum `iva_class_map`, `line_value_is_net`, section-heading and savings-line patterns, date format, decimal separator |
| `priority` | `Integer` | Tie-break when several profiles match (higher wins) |
| `success_rate` | `NUMERIC(4,3)?` | Rolling share of receipts this profile auto-accepted |
| `is_active` | `Boolean` | Disable without deleting (`default: true`) |
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `created_at` / `updated_at` | `Timestamp` | Audit timestamps |

**Constraints & Rules:**
- Exactly **one** profile with `merchant_id IS NULL` exists — the generic fallback. It must always be able to run, so a brand-new merchant is never a dead end.
- `parser_key` names a parser **registered in code**; `field_hints` tunes it without a deploy. A merchant-specific parser is a class, not a config blob — configuration alone cannot handle Continente's net line values and Pingo Doce's gross ones equally.
- A profile is **never** required to add a merchant. Absent a match, the generic profile runs and the receipt simply arrives with lower confidence.
- `success_rate` is observed, not configured, and is shown in the UI so a failing profile is visible.

---

### Observed Receipt Anatomy (from real fixtures)

Eight real *talões* live in
[seed/supermarket/invoices/](../seed/supermarket/invoices/) — four Continente,
four Pingo Doce. **Read them before writing a parser.** They overturn several
assumptions this file previously made, and the differences between the two
merchants are the strongest possible argument for per-merchant profiles
(FR-1.16).

**Continente line format** — `(IVA class) DESCRIPTION VALUE`, with savings on
the next line and multi-buys wrapped onto a continuation line:

```
Mercearia Salgada:                        ← merchant's own section heading
(C) POLPA TOMATE GULOSO 500G      1,19
POUPANCA                          0,30    ← saving, annotation only
(C) BAT FR AZEITE CONTINENTE 150G
2 X 1,45                          2,90    ← quantity × unit price, wrapped
```

**Pingo Doce line format** — `IVA class DESCRIPTION [qty X unit] VALUE`, savings
parenthesised, weighed goods carrying a 3-decimal quantity:

```
FRUTAS E VEGETAIS                         ← merchant's own section heading
 C COGUMELOS BRANC 300G  1,000 X 0,74  0,74   ← 1 kg × €0,74/kg
 C IO PROT COC GA2X150G               1,29
     Poupança Imediata               (0,10)
DEPÓSITO VOLTA
 I ºVALOR DEPÓSITO       2 X 0,10     0,20   ← tara, IVA class I = 0 %
```

| What the receipts prove | Consequence |
| :--- | :--- |
| **No EAN, no article code, anywhere.** The only per-line identifier is a truncated description | `ProductAlias` is the load-bearing match mechanism, not an optimisation (Decision #23) |
| **The IVA class is printed per line**, and the letters differ per merchant — Continente `(A)`=6 %, `(C)`=23 %; Pingo Doce `C`=6 %, `E`=23 %, `I`=0 % | Never infer the rate. Map the letter through `field_hints.iva_class_map` (Decision #26) |
| **Both merchants group lines under their own headings** — `Mercearia Salgada`, `Laticinios/Beb. Veg.`, `FRUTAS E VEGETAIS`, `PRODUTOS LACTEOS` | Capture as `merchant_section`; a high-quality categorization signal at no extra cost (Decision #27) |
| **Discount semantics are opposite.** Continente: `SUBTOTAL` is already net of `POUPANCA`, and only the cartão is subtracted (`40,56 − 4,00 = 36,56`). Pingo Doce: `TOTAL` is gross and `POUPANÇA` *is* subtracted (`15,70 − 0,50 = 15,20`) | `field_hints.line_value_is_net` per profile. A single parser silently mis-states one merchant's spending (Decision #28) |
| **Two different NIFs appear on one receipt** — Continente prints the merchant's `NIF: PT501591109` in the header *and* the household's `NIF:PT209362367` on the document line | The first digit decides: `5` = company, `2` = person. Never positional guessing (Decision #29) |
| **The IVA summary table foots to the amount paid** — Continente `20,75 + 15,81 = 36,56`; Pingo Doce `10,72 + 4,28 + 0,20 = 15,20` | A second, independent arithmetic anchor alongside the line sum |
| **Size lives inside the description** — `500G`, `1KG`, `397G`, `GA2X150G`, `3*25` | Weight extraction is description parsing; `pack_variants` supplies the candidates |
| **Loyalty accrues in euros, not points** — `ACUMULOU NO SEU CARTAO 4,06€`, `Combustível ganho na compra: 0 EUR` | `LoyaltyAllocation` records EUR (Decision #30) |
| **Card numbers are pre-masked** — `XXXXXXXX3394X`, `***************690` | Confirms Decision #4: nothing sensitive ever reaches us |
| **ATCUD is printed as text** as well as encoded in the QR — `ATCUD:JFP767JJ-035904` | Read the text as a fallback when the QR will not decode |
| **No `F` marker appears on either receipt** | Expected: Fs articles are **not on the invoice at all** — the household appends them (Decision #31) |

---

### Category Taxonomy (pt-PT)

- **Language policy.** Schema columns and `code_en` identifiers are **English**; `display_name_pt` carries the household's Portuguese vocabulary verbatim. UI is pt-PT-first and i18n-ready.
- **Level meanings.** **L1** = macro group (`Aperitivos`), **L2** = subcategoria (`Batatas Fritas`), **L3** = **normalized product-genus** (`Batata Frita Ondulada`) — brand-, size- and SKU-agnostic.
- **L3 is a category, NOT the product.** `Batata Frita Continente` is a `MasterProduct` with `L3 = Batata Frita Lisa`, `brand = Continente`. This keeps L3 useful for cross-brand €/kg comparison without losing SKU granularity.
- **Brand-as-L2 exception.** For premium-by-brand branches (`Gelados`, `Pastilhas`): L2 = brand, L3 = linha/sabor, `MasterProduct` = exact SKU. Those L2 nodes carry `brand_axis = true`.
- **Empty L3 arrays are valid** placeholder L2 nodes; L3 is optional — the deepest *assigned* level is the authoritative one.
- **Invariants:** `parent.domain == child.domain`; `level == 1 ⇔ parent_id IS NULL`.
- **Seed:** [seed/supermarket/categories/supermarket-categories.pt-PT.json](../seed/supermarket/categories/supermarket-categories.pt-PT.json) supplies the vocabulary. Its `review_candidates` list documents the normalization decisions (accent/casing fixes, EN→pt-PT L1 renames `Gym→Ginásio` / `Misc→Diversos` / `Others→Outros`, merged duplicates, removed garbage tokens).

> ⚠️ **Known stale wording in the seed file.** `exclusion_flag.meaning_en` still says `total_cents` / `fs_total_cents`. That predates both the decimal-EUR rule and Decision #31 — there is no stored Fs total at all now, and money is `NUMERIC(10,2)` EUR. Treat the JSON as authoritative for *vocabulary only*.

### Category Governance — editing a live tree

The taxonomy is the household's, and it will change. Each operation has a
defined blast radius; all four are audited and available to `OWNER`/`MEMBER`:

| Operation | Effect on existing data |
| :--- | :--- |
| **Rename** (`display_name_pt`) | **None.** Rows reference categories by `id`, so a rename propagates everywhere at no cost — no migration, no backfill. This is why the id/display split exists |
| **Reparent** (move a node under a different parent) | The deepest assigned id on each row is unchanged; the **maintained ancestors** (`category_l1_id` / `_l2_id`) are recomputed for every affected row in one audited transaction. History is re-expressed under the new tree — which is the point of reorganising it |
| **Merge** (fold A into B) | Every row pointing at A is reassigned to B, then A is soft-deleted. Reassignment is audited row-by-row and is reversible from `AuditLog` |
| **Retire** (soft-delete) | **Blocked while any row references it.** The UI offers merge-into-target as the way out; a category in use is never silently orphaned |

**Why ancestors are maintained rather than snapshotted.** Storing the full
triple as a historical snapshot would keep old rows stable but let them drift
from the current tree, so "spend by L2" would silently mix two taxonomies.
Deriving ancestors on every read would cost a recursive join on the hottest
query in the module. The middle path — deepest level authoritative, ancestors
denormalized and refreshed on reparent — gives consistent analytics and
single-table queries. See Decision #16.

---

### Computed & Derived Fields
Evaluated on read; nothing is persisted except the immutable
`ProductPriceHistory` snapshot.

- `weight_kg` (per item) = `COALESCE(weight_observed_kg, weight_listed_kg)`
- `price_per_kg_pvp_eur` = `unit_price_pvp_eur / weight_kg` — legacy `Preco/Kg/real`, a misnomer: it is the **list** price per kg
- `price_per_kg_promo_eur` = `(unit_price_pvp_eur − promo_discount_eur) / weight_kg` — after the individual promo only
- `price_per_kg_final_eur` = `paid_price_eur / weight_kg` — after the prorated invoice discount too
- All three are **`NULL` when `weight_kg` is `NULL`**, with a stated reason — never defaulted to zero
- `iva_eur` = `paid_price_eur × iva_rate / (100 + iva_rate)`
- `subtotal_eur` (per receipt) = `total_eur + total_discount_eur` — the pre-discount figure. Note the **direction**: subtotal is *larger* than the total, because the discount has not been taken off yet
- `computed_total_eur` (per receipt) = `Σ paid_price_eur` over **every** item — Fs rows contribute `0.00` and refunds contribute negative, exactly as the receipt printed them
- `notional_value_eur` (per item) = `is_fs ? unit_price_pvp_eur × quantity : paid_price_eur`
- `notional_total_eur` (per receipt) = `total_eur + fs_value_eur` — **what the shop would have cost had every article been paid for**
- `fs_value_eur` (per receipt, or any period) = `Σ notional_value_eur` over Fs items
- `fs_item_count` (per receipt) = `COUNT(items WHERE is_fs)` — how many Fs articles were appended
- `fs_share_pct` = `fs_value_eur / total_eur × 100` — Fs value **against what was actually paid**, so two €5 Fs articles on a €10 invoice read as `100 %`. `NULL` when `total_eur = 0`
- `printed_item_count` (per receipt) = `COUNT(items WHERE NOT is_fs)` — the figure compared against the printed `item_count`
- `refund_item_count` (per receipt) = `COUNT(items WHERE quantity < 0)`
- `is_return` (per receipt) = every item has `quantity < 0`
- `is_reconciled` = `computed_total_eur` matches `total_eur` within `receipts.arithmetic_tolerance_eur`
- `invoice_discount_ratio` = `total_discount_eur / Σ(pvp − promo)` over non-Fs items
- `margin_signal` (per product/merchant) = `(current_weight / avg_weight_12m) − (current_price / avg_price_12m)`
- `is_complete` (per receipt) = no item is missing a `master_product_id` or a category
- `validated_share` (per receipt) = share of items whose `category_status` is not `AUTO`

> If sorting or filtering by €/kg becomes a hot path, promote it to a Postgres
> `GENERATED ALWAYS AS … STORED` column rather than persisting it in application
> code — the derivation stays in one place.

---

## Functional Requirements
- **FR-1.1 OCR Ingestion.** Parse uploaded PDFs/images to extract merchant, date/time, line items, quantity/weight + unit, PVP, promotions, discounts, totals and payment-method breakdown. Persist `raw_ocr_payload` and per-field confidence. Runs as a Celery task keyed by a `ProcessingJob.idempotency_key`; a failure is a `FAILED` job row, never a silent loss.
- **FR-1.2 Manual Fallback & Editing.** Full create/edit of receipts and items, including **adding an Fs article that was never on the invoice** — classified like any other product and given a notional value. Any edit recomputes totals, IVA and €/kg, then re-scores confidence. Corrections feed the learned alias table.
- **FR-1.3 Hierarchical Categorization.** Assign the deepest category per item, auto-suggested from `MasterProduct.default_category_l3_id` when the product resolves, and otherwise from a **local classifier over the L3 vocabulary** fed by the description *and* the `merchant_section` heading the line sat under — so a brand-new product still arrives categorized rather than blank. Always overridable through an autocomplete picker. `category_status` records whether the assignment was `AUTO`, `VALIDATED` or `MANUAL`; confirming an `AUTO` suggestion promotes it to `VALIDATED` and feeds the learning loop.
- **FR-1.4 Price Evolution & Shrinkflation.** Maintain `ProductPriceHistory`; compute `margin_signal`; render €/kg list and paid trend lines; alert on shrinkflation. Fs observations participate like any other, and every one of these views honours the `fs` filter.
- **FR-1.5 Contextual Flags & Tags.** Receipt- and item-level `tags[]` (`#férias`, `#culinária`, `#social`) are open user labels with **no effect on any total** — structurally distinct from `is_fs`, which says the article was never on the invoice, and from `product_flag`, which is read off the document. Dietary and allergen attributes are queryable per item.
- **FR-1.6 Document Storage & the Fiscal QR.** Reuse the shared `Document` pipeline. **New work:** read the Portuguese **ATCUD fiscal QR** (Portaria 195/2020), which encodes *invoice-level* fields only — issuer NIF, buyer NIF, document type, status and date, unique document ID, ATCUD, the VAT breakdown per rate, and the gross total. It carries **no line items**. Treat it as the module's **highest-confidence anchor**: when present and structurally valid, its NIF resolves the merchant exactly, its date sets `purchase_date`, and its total and VAT breakdown become the reference values that item-level arithmetic reconciles *against*. Record `atcud_valid` and `atcud_reason`. A missing or malformed QR lowers confidence and flags for review, but never blocks ingestion.
- **FR-1.7 Merchant Management.** Extend the existing `/api/merchants` router with receipt-specific needs (logo upload, per-merchant parser hints, alias management). NIF validation already exists. Receipts may only reference an existing merchant.
- **FR-1.8 Fuzzy Product Normalization.** Resolve merchant descriptions to a `MasterProduct` via **normalize-then-match**: strip accents, casing, units and pack affixes → `rapidfuzz` token-set ratio → learned `ProductAlias`. Confirmed corrections append to the alias table.
- **FR-1.9 Duplicate Detection.** Detect duplicates by document SHA-256, by merchant + date + amount triangulation, and by OCR payload similarity. Auto-merge only on an exact hash match; everything else becomes a `ReviewTask`.
- **FR-1.10 Multi-Payment & Loyalty Allocation.** Parse composite payments (cash + card + loyalty). Allocate the cartão discount across items proportionally or per item, kept strictly separate from per-item promos. Fs items never receive an allocation — they were not on the invoice being discounted.
- **FR-1.11 IVA Class Mapping & Validation.** Read the IVA **class letter printed on each line** and resolve it through the profile's `field_hints.iva_class_map` — the letters are merchant-specific (Continente `(A)`=6 %, `(C)`=23 %; Pingo Doce `C`=6 %, `E`=23 %, `I`=0 %). Only when no letter is printed may the rate be inferred, and then `iva_inferred = true`. Validate the per-class sums against the **printed IVA summary table**, which foots to the amount paid and is an independent arithmetic anchor.
- **FR-1.12 Deposits & Refunds.** Model bottle deposits (*tara*) and packaging refunds as `product_flag = DEPOSIT_RETURN`; refunds carry negative quantities and are counted by derivation, never by a stored counter.
- **FR-1.13 Bulk Weigh & Unit Ambiguity.** Distinguish listed weight (label) from observed weight (register scale); handle items priced only at checkout. A missing weight suppresses €/kg with a stated reason rather than guessing one.
- **FR-1.14 Unit Standardization.** Normalize every quantity into `(quantity_canonical, unit_canonical ∈ KG|L|UN)` so cross-unit and cross-merchant comparison is well defined. Mass → kg, volume → L, count → un; never convert between the three families.
- **FR-1.15 Reconciliation to the Ledger.** Propose `Link(RECEIPT_TRANSACTION)` edges to M2 transactions within a configurable date window and amount tolerance, scored and explained. Above the cutoff the link is auto-created as `CONFIRMED`; otherwise it becomes a `ReviewTask`. Manual linking reuses the shared transaction picker.
- **FR-1.16 Merchant Parser Profiles.** Maintain a registry of parsers keyed by merchant plus **one generic fallback**. Detection runs **before** extraction: identify the merchant from the document, select the highest-priority matching active profile, then parse with it. An unmatched document falls through to the generic profile — never to an error. Profiles are CRUD-able, can be disabled without deletion, and expose their observed `success_rate`.
- **FR-1.17 Parsing Queue & Batch Ingestion.** Accept many invoices in one upload. Each becomes its own `ProcessingJob` and `Receipt`, processed independently so one bad scan never blocks the batch. Expose a queue view over job state (`QUEUED`/`RUNNING`/`SUCCEEDED`/`FAILED`/`RETRYING`) with per-job progress, the failure reason, and **retry from the stored document** — never a re-upload.
- **FR-1.18 Category Administration.** Create, rename, reparent, merge and retire categories in the `GROCERY` domain, with the impact rules in Category Governance enforced and audited. Retire is blocked while rows reference the node; merge is the supported way out.
- **FR-1.19 Line-Level Explorer.** Browse every purchased article across all invoices as one flat, filterable, paginated grid — the shape the household already thinks in — with a one-click jump from any line to the original invoice image and to the product's full purchase history.

---

## Automation Rules

- **Merchant resolution:** runs **first**, because it selects the parser. Priority is **printed NIF → alias → fuzzy name**. A receipt may carry **two** NIFs — the merchant's and the household's — and the Portuguese numbering plan tells them apart deterministically: **1, 2, 3 are natural persons; 5, 6, 8, 9 are organisations.** Take the organisational NIF, and prefer the header block when both are organisational. Checksum-validate, then look up `Merchant.nif`. Fall back to alias/name fuzzy match — auto-accept ≥ 0.78, review band 0.70–0.78, manual below. A NIF that validates but matches **no** merchant, or a *different* merchant than the name suggests, emits `merchant_nif_mismatch` and sends the receipt to review; it is never silently overridden.
- **Parser selection:** highest-`priority` active profile whose `detection_patterns` match and whose `document_kinds` include this input; otherwise the generic profile. The chosen profile is recorded on `Receipt.parser_profile_id` and shown in the UI.
- **Product resolution priority:** `ProductAlias` exact match on `description_norm` → normalized fuzzy ≥ 0.78 (review band 0.70–0.78) → new-product prompt. **There is no exact key** — real receipts print neither an EAN nor an article code, only a truncated description (Decision #23). `ProductAlias` is therefore not an optimisation but the load-bearing mechanism of the whole module.
- **Fs rule (CRITICAL).** An Fs item is **added by hand and never parsed**, so it takes no part in extraction, confidence scoring or the ≥80 % auto-accept measure. There is exactly **one** arithmetic check, `Σ paid_price_eur ≈ total_eur` within tolerance, and Fs rows enter it contributing `0.00`. **Adding an Fs item to a receipt — even a `CONFIRMED` one — must leave `total_eur`, `computed_total_eur` and `is_reconciled` untouched**; a test asserts precisely this. An Fs item requires a `notional_value_eur > 0` with a recorded source, otherwise it is meaningless.
- **Arithmetic tolerance** is a `Setting` (`receipts.arithmetic_tolerance_eur`), default **€0.02** per the brief. A €0.05 allowance may be granted only for a merchant known to round, and that allowance is itself a decision reason.
- **Loyalty allocation:** prorate the cartão discount into `invoice_allocated_discount_eur` per item, skipping Fs rows.
- **Shrinkflation:** over a rolling **12-month** window with **≥3 prior observations** of the same `(master_product_id, merchant_id)`, alert when `margin_signal ≤ −0.05` — the pack shrank faster than the price fell. `margin_signal` is `NUMERIC(6,4)`: a score, not money, but decimal for reproducibility. Fs observations count towards the window unless the caller passes `fs = exclude`.
- **Duplicate detection:** identical document SHA-256 → auto-merge prompt at confidence `1.000`. Otherwise merchant + date within ±3 min **and** amount within ±€0.10 **and** OCR similarity ≥ 0.95 → `ReviewTask`.

### The Confidence Engine

A **pure, deterministic** scoring module — no clock reads, no randomness, no
I/O:

```python
def score(signals: ReceiptSignals) -> tuple[Status, Decimal, list[DecisionReason]]
```

Each `DecisionReason` is `{rule, detail, score}` and surfaces behind the
**"Porquê?"** affordance on every auto-classified value.

| Signal | Weight | Source |
| :--- | :--- | :--- |
| Product match | 0.30 | learned alias > normalized fuzzy description |
| OCR text confidence | 0.25 | per-field, from the extraction provider |
| Arithmetic reconciliation | 0.25 | Σ items vs printed totals |
| Merchant match | 0.20 | name/alias fuzzy score |

Thresholds come from `Setting` (`confidence.auto_accept` 0.90,
`confidence.review` 0.60), per-source configurable. **Learned corrections live
in `ProductAlias`, outside the pure engine.** Arithmetic reconciliation is a
*signal*, not a gate: a mismatch **halves** the score and emits
`arithmetic_mismatch` — it never silently discards a receipt.

### Processing Engine

The pipeline runs in a fixed order, and **merchant detection comes first**
because it selects the parser:

```
detect merchant ─▶ select MerchantParserProfile (or generic)
                ─▶ extract ─▶ normalize ─▶ resolve product ─▶ classify
                ─▶ reconcile arithmetic ─▶ score confidence
```

Each stage is a Protocol. Every stage **must** have a local implementation that
works offline and unsubscribed — that is what makes the module usable on day
one. A remote implementation may be registered alongside it and selected per
stage:

| Protocol | Local implementation (ships enabled) | Remote alternative |
| :--- | :--- | :--- |
| `ReceiptParser` | Per-merchant classes (`continente_v1`, `pingodoce_v1`, …) + `generic_v1` | — layout parsing stays local |
| `OcrProvider` | `pytesseract` — scans and photos | Hosted OCR, when configured |
| `ExtractionProvider` | `pdfplumber` — digital PDFs | LLM extraction, when configured |
| `SuggestionProvider` | `rapidfuzz` token-set + learned `ProductAlias` | External product database |
| `CategoryClassifier` | Keyword/similarity match over the L3 vocabulary | LLM classification |

**Selection is per stage, via `Setting`, and defaults to local.** Enabling a
remote engine requires a credential to be present; without one the stage
silently stays local rather than failing. The UI shows which engine handled a
receipt, and the engine name is recorded in `decision_reasons` so a quality
change is always traceable to the switch that caused it.

**Do not treat local-only as a ceiling.** If a remote engine would materially
raise the auto-accept rate, the right move is to build the adapter, measure both
against the same fixtures, and record the comparison — not to assume the local
engine is good enough. The default exists because there is no subscription
today, not because remote processing is unwelcome.

---

## UI / Screens

Design intent: modern, dense-but-readable, and progressive. Secondary detail
lives in modals, side sheets, popovers and collapsible sections — never in a
wall of fields. Every destructive or lifecycle action is one click away with a
confirm.

- **UX-1.1 Upload & Parsing Queue.** Drag-drop or camera capture, **many files at once**. A queue list shows one row per invoice with its job state, the parser profile chosen, live progress, and the failure reason when it failed — with **retry** (re-runs from the stored document) and **parse manually** as escape hatches. Finished rows link straight into review.
- **UX-1.2 Receipt Review (crown jewel).** Split pane: the original image/PDF on one side, parsed line items on the other.
  - Uncertain fields are flagged **by icon and label, never by colour alone**.
  - Inline edits recompute running totals live and warn when `Σ items ≠ total`.
  - Inline `MasterProduct` **autocomplete** (search-as-you-type over canonical names, brands and known aliases) with a "create new product" affordance; suggested category and allergen tags follow the pick.
  - Category picker is an **autocomplete over the tree**, showing the full `L1 › L2 › L3` path so the same leaf name under two parents is never ambiguous.
  - A **"Porquê?"** popover on every auto-filled value showing its `decision_reasons`.
  - A single **"confirmar categorias"** action promotes every `AUTO` classification on the receipt to `VALIDATED`.
  - An **"adicionar artigo Fs"** action appends an article that was not on the invoice, with the same product and category pickers as any other line plus a notional value pre-filled from price history. Fs rows are visually segregated from the printed lines and shown with their own subtotal.
  - Optimistic updates for single-item edits only — never for aggregates.
- **UX-1.3 Receipts List (level 1 — one row per invoice).** Filterable by merchant, date range, tag, category, `fs` (`only` \| `exclude` \| `all`) and status; summary cards for total spend, Fs value and item count; sorting, pagination and a density toggle.
- **UX-1.4 Item Explorer (level 2 — one row per purchased article).** The flat view the household already thinks in: every line across every invoice, filterable by product, category, merchant, date, `fs` (`only` \| `exclude` \| `all`), flag and `category_status`. Columns mirror the legacy sheet (date · merchant · product · category · qty · weight · PVP · promo · paid · €/kg). Each row links to the source invoice — opening the review pane focused on that line — and to the product's purchase history. CSV export.
- **UX-1.5 Duplicate Review.** Surfaced **inside the shared Review Queue** — original and suspect side by side with the similarity score and a merge/dismiss action.
- **UX-1.6 Master Product Manager.** CRUD over canonical name, brand, **pack variants (label + weight + merchant SKU per pack size)**, per-merchant aliases with confidence, dietary/allergen checkboxes, seasonal flags, and a merge-duplicates action. Each product shows every receipt line it has ever appeared on.
- **UX-1.7 Category Administration.** Tree editor for the `GROCERY` domain: rename, drag-to-reparent, merge and retire. Every destructive operation shows **how many rows it will touch before it runs**, and retire is refused while the node is in use with merge offered as the alternative.
- **UX-1.8 Merchant Parser Profiles.** List of profiles with merchant, document kinds, priority, active toggle and observed `success_rate`; edit `field_hints`; a "test against this receipt" action that re-parses a stored document with a chosen profile and diffs the result.
- **UX-1.9 Price Evolution.** Product selector; €/kg list vs paid multi-line trend by merchant; shrinkflation overlay; an `fs` toggle (`only` \| `exclude` \| `all`) that redraws the series; CSV export.
- **UX-1.10 Loyalty Savings.** A view grouped by scheme and masked card number — no separate management screen, because there is nothing to manage beyond what each receipt already printed. Associated receipts, euros accrued and spent, per-receipt allocation breakdown.

---

## Proposed API Surface
Indicative; may be refined during implementation as long as the capabilities and
rules above are preserved. Routes are namespaced `/receipts` under `/api`.

### 1. Receipts & the Parsing Queue
- `POST /receipts` — multipart upload, **one or many files**; requires an `Idempotency-Key`; returns one `ProcessingJob` per file.
- `GET /receipts/queue` — job state, progress, chosen parser profile and failure reason per queued invoice.
- `POST /receipts/{receiptId}/reparse` — re-run from the stored document, optionally forcing a `parser_profile_id`. Never requires re-upload.
- `GET /receipts` — filters: merchant, date range, tag, category, `fs`, status, entity.
- `GET /receipts/{receiptId}` — items, confidence breakdown, decision reasons and links.
- `PATCH /receipts/{receiptId}` · `PATCH /receipts/{receiptId}/items/{itemId}` — recompute totals and rescore.
- `POST /receipts/{receiptId}/items` — append an item that was not on the invoice (`is_fs = true`), with its notional value and source.
- `POST /receipts/{receiptId}/confirm` — transition to `CONFIRMED`, resolve the `ReviewTask`, feed the learning loop.
- `POST /receipts/{receiptId}/confirm-categories` — promote every `AUTO` classification on the receipt to `VALIDATED`.
- `POST /receipts/{receiptId}/void` — void with a mandatory reason; replaces delete once confirmed.

### 2. Line Items (level 2)
- `GET /receipt-items` — flat, paginated, filterable by product, category, merchant, date, flag and `category_status`; CSV export.
- `PATCH /receipt-items/{itemId}/category` — assign or confirm a category, setting `category_status`.

### 3. Duplicates
- `POST /receipts/{receiptId}/check-duplicates` — on-demand re-scan.
- `POST /receipts/{receiptId}/merge-duplicate/{dupId}` — void one, relink its items.

### 4. Products & Aliases
- `GET/POST/PATCH/DELETE /master-products` — full CRUD including `pack_variants`.
- `GET /master-products/search?q=` — **autocomplete** over canonical name, brand and known aliases.
- `GET /master-products/{productId}/occurrences` — every receipt line this product has appeared on, with links to each invoice.
- `POST /master-products/{productId}/merge` — deduplicate master records.
- `GET /master-products/{productId}/price-history` — with shrinkflation signals; accepts the `fs` filter.
- `POST /product-aliases/learn` — update alias confidence from a user correction.

### 5. Categories
- `GET /categories/search?q=&domain=GROCERY` — **autocomplete** returning the full `L1 › L2 › L3` path.
- `POST /categories` · `PATCH /categories/{categoryId}` — create and rename.
- `POST /categories/{categoryId}/reparent` — move; recomputes maintained ancestors on affected rows.
- `POST /categories/{categoryId}/merge` — fold into a target, reassigning every referencing row.
- `DELETE /categories/{categoryId}` — retire; **refused while in use**, with the usage count returned.
- `GET /categories/{categoryId}/impact` — how many receipt items and master products a destructive operation would touch, **before** it runs.

### 6. Parser Profiles
- `GET/POST/PATCH/DELETE /parser-profiles` — CRUD; the generic profile cannot be deleted.
- `POST /parser-profiles/{profileId}/test` — re-parse a stored document with this profile and return a diff against the current result.

### 7. Loyalty
- `GET /loyalty-allocations/summary` — totals grouped by scheme and masked card number.
- `GET /receipts/{receiptId}/loyalty-allocation` — per-item breakdown.

### 8. Analytics & Import
- `GET /receipts/analytics/shrinkflation` · `GET /receipts/analytics/category-spend`
- `POST /receipts/import/legacy` — the Excel migration, wrapped in an `ImportBatch`.

**Reused, not rebuilt:** the Core `Merchant`, `Tag`, `Document` and `ReviewTask`
surfaces, and the shared transaction picker. Category **reads** are Core; the
administration endpoints above extend that router and are scoped to `domain =
GROCERY`.

---

## Analytics & KPIs
- **Ingestion quality: share of receipts reaching `AUTO_ACCEPTED` with zero edits** — the headline rubric number.
- €/kg evolution (list and paid) per product and merchant, including seasonal variance.
- Shrinkflation: products whose weight or unit count fell against the trailing 12 months.
- Loyalty savings: cumulative discount per receipt, per scheme and masked card number.
- Fs budget tracking: `fs_value_eur`, item count, and **`fs_share_pct`** — Fs value against what was paid, per receipt and over any period. Every analytic accepts an `fs` filter of `only` \| `exclude` \| `all` (default `all`), so the household can ask "what did I actually pay?", "what was I given?" or "what did I consume in total?" from the same query.
- Basket composition: category split, dietary breakdown, organic share of spend.
- Promotion ROI: discount rate by type (BOGO, percentage, absolute, loyalty) and by merchant.
- Duplicates: share flagged and resolved.

---

## Performance

The NFR is **<800 ms p95 on a 10-year seed**, measured with `EXPLAIN (ANALYZE,
BUFFERS)`, never assumed.

- `receipts (entity_id, purchase_date DESC, id)` — the shape of every list and dashboard query.
- `receipt_items (receipt_id, line_no)`, `receipt_items (master_product_id)`, `receipt_items (category_l1_id, category_l2_id, category_l3_id)`.
- `product_price_history (master_product_id, merchant_id, observed_on DESC)` — `is_fs` lives on the row so the Fs filter never forces a join back to `receipt_items`.
- `documents (sha256_hash)` — already exists; drives duplicate detection.
- Dashboards read **materialized monthly aggregates** plus a Redis cache invalidated on confirm. `raw_ocr_payload` is never selected in list queries.

---

## Edge Cases & Business Rules
- **Reconciliation.** `Σ paid_price_eur == total_eur ± tolerance` (default €0.02) over every item; Fs rows enter at `0.00` and are excluded from the printed `item_count` check.
- **Multi-weight units.** kg-priced and unit-priced items are handled separately; an item with both a count and a weight (3 packs × 250 g) carries both and normalizes to kg.
- **Missing prices.** Bulk-weighed items without an upfront price are flagged for manual entry; €/kg stays `NULL` with a stated reason.
- **OCR garbling.** Thermal receipts corrupt `€`, `ç`, `ã`. Normalization strips diacritics before matching; unrecoverable text lowers confidence rather than guessing.
- **Refunds & returns.** Negative quantities are refunds — excluded from the paid total, surfaced through the derived `refund_item_count`, and they may link back to the original purchase. A receipt whose items are all negative derives as `is_return`.
- **Deposits (*tara*).** Never categorized as groceries; reconciled when the refund is credited.
- **Payment ambiguity.** "DINHEIRO + CARTÃO" without a printed split prompts the user rather than assuming an allocation.
- **Missing ATCUD or NIF.** Flags for review with a tax-compliance warning; never blocks ingestion. A NIF that validates but matches no known merchant raises `merchant_nif_mismatch` rather than guessing.
- **IVA cross-check.** A per-item IVA sum differing from the invoice total by more than ±€0.01 sets `NEEDS_REVIEW`.
- **Idempotent re-import.** The same document SHA-256 within the same entity never creates a second receipt.
- **Entity attribution.** A receipt belongs to exactly one entity. With the selector on «todas» the write is **refused, not guessed**; the upload dialog asks for the entity inline.
- **Deletion.** Confirmed receipts are **voided with a reason**, never deleted. Soft delete applies before confirmation.

---

## Deferred (explicitly not built now)
- **A bundled remote engine.** The provider seam, the per-stage `Setting` and the credential check all ship; what does not ship is a configured cloud OCR, hosted LLM or external product-database adapter. Adding one is ordinary follow-up work, not a redesign — see Decision #13.
- **Barcode scanning.** Scanning a product package to look up or create a `MasterProduct`, and any EAN check-digit validation that would come with it. `pack_variants[].barcode` is the slot it would populate. Receipts never supply one, so nothing today would read it.
- ATCUD **digital-signature** verification (the QR is read and structurally validated in v1; the cryptographic hash chain is not verified).
- SKU batch/lot tracking and product-recall alerts.
- Return-window and freshness alerts from `expected_shelf_life_days` (the field is stored, the alerting is not built).
- Bulk-vs-retail price-anomaly flagging.
- Seasonal-produce anomaly analytics (`seasonal_flags` is stored and filterable; the model is deferred).
- Hand-written receipt OCR tuning — supported, but routed straight to manual review.
- Multi-merchant mall receipts as a single payment transaction (see Decision #7).
- Data-driven parser authoring (building a new merchant parser from the UI alone). v1 registers parsers in code and tunes them with `field_hints`.

---

## Definition of Done
- [ ] FR-1.1 – FR-1.19 implemented; `docker compose up` still yields a working stack from clean.
- [ ] **≥80% of receipts on the seed sample reach `AUTO_ACCEPTED` with zero user edits**, measured against the **real fixtures** in `seed/supermarket/invoices/` — proven by an executable check, not by eye.
- [ ] Both merchant profiles parse their own fixtures byte-for-byte correctly, including the **opposite discount semantics**: Continente reconciles as `Σ lines − cartão = total` and Pingo Doce as `Σ lines − poupança = total`. A test asserts each merchant's totals against the printed figures.
- [ ] The printed **IVA class letter** drives the rate for every line; the per-class sums foot to the printed IVA summary table on every fixture.
- [ ] Merchant NIF is taken from the header block — a fixture carrying **both** merchant and buyer NIFs resolves to the merchant.
- [ ] `merchant_section` is captured for every line and measurably improves classification of unseen products.
- [ ] **The full pipeline completes with egress blocked, at default settings** — proving the module needs no subscription. The provider seam is exercised by a fake remote engine in tests, proving a stage can be swapped without touching the pipeline.
- [ ] A merchant-specific parser and the generic fallback both parse their fixtures; a document matching no profile still parses generically rather than failing.
- [ ] Batch upload of N invoices creates N independent jobs; one deliberately corrupt file fails alone and is retryable from the stored document without re-upload.
- [ ] **Fs proven by unit tests:** adding an Fs article to a `CONFIRMED` receipt leaves `total_eur`, `computed_total_eur`, `is_reconciled` and the printed-count check **unchanged**, while `notional_total_eur` rises by its value; the €10 invoice + 2×€5 Fs case yields `notional_total_eur = 20.00` and `fs_share_pct = 100`.
- [ ] An Fs article writes a `ProductPriceHistory` observation carrying its notional value in **both** price columns, marked `is_fs`, and never `0.00`.
- [ ] Fs articles appear in consumption, quantity and price history like any other product, and every such query — including €/kg trends and shrinkflation — honours the `fs` filter.
- [ ] The printed `item_count` check is unaffected by Fs articles, and `fs_item_count` reports them separately.
- [ ] Prorated invoice discount proven: summing per-item promos alone does **not** reconcile; only `pvp − promo − invoice_allocated` does.
- [ ] All three €/kg variants computed and distinct on a fixture carrying both a per-item promo and an invoice-level discount.
- [ ] Confidence engine is pure: identical input yields byte-identical `(status, confidence, decision_reasons)` across runs.
- [ ] Every auto-decision exposes human-readable reasons in the UI and is user-overridable; corrections update `ProductAlias`.
- [ ] Every item is categorized on ingest — including one whose product is brand new — and `category_status` transitions `AUTO → VALIDATED` on confirmation.
- [ ] Category rename leaves every referencing row untouched; reparent recomputes maintained ancestors on all affected rows in one audited transaction; retire is refused while in use and merge reassigns and audits.
- [ ] A product with two pack sizes of different weights resolves correctly from the size token in the description and yields comparable €/kg.
- [ ] Both browse levels work: one row per invoice, and one row per article across all invoices with a working jump to the source document.
- [ ] Receipt status machine rejects illegal transitions; confirmed receipts are voided, never deleted; every mutation writes `AuditLog`.
- [ ] Re-upload of the same file is idempotent — no duplicate receipt, no duplicate `ProcessingJob`.
- [ ] Duplicate detection measured against **labelled seed pairs** (≥95% TPR, ≤2% FPR) — the seed must therefore ship those pairs.
- [ ] IVA inference reconciles with invoice totals within ±€0.01.
- [ ] ATCUD fiscal QR read and structurally validated; its NIF, date, total and VAT breakdown used as the reconciliation reference when present; a missing or malformed QR flags for review without blocking.
- [ ] Receipt↔transaction `Link` suggestions created above the cutoff, reviewed below it; manual linking uses the shared transaction picker.
- [ ] Legacy Excel import runs inside an `ImportBatch`, is re-runnable without duplication, and recomputes `PromoGlob` deterministically.
- [ ] Dashboard queries measured under 800 ms p95 on the 10-year seed with `EXPLAIN (ANALYZE, BUFFERS)`.
- [ ] Seed: realistic Portuguese receipts including appended Fs articles, a loyalty discount, a refund, a deposit return and a labelled duplicate pair.
- [ ] `make check` green; `docs/` and the root `README.md` updated in the same change.

**Testing discipline (brief §7 — this supersedes any coverage target).** Do
**not** chase a coverage percentage. Test only what is load-bearing and easy to
get subtly wrong: the Fs valuation rules, the prorated-discount arithmetic, the
three €/kg variants, decimal money handling, the pure confidence-scoring
functions, idempotent re-import and retry, and the receipt status-machine
guards. Everything else is verified by exploratory testing against this
Definition of Done. Each test file states which rubric bullet it protects.

> **Note on e2e.** Playwright is **not yet set up** (`apps/web/tests/e2e/` does not
> exist). Upload → review → confirm is the best candidate for the first e2e test, so
> M1 either stands up that tooling or explicitly records the deferral — it must not
> silently claim e2e coverage.

---

## Open Questions / Decisions

| # | Question | Decision |
| :--- | :--- | :--- |
| 1 | Auto-merge high-confidence duplicates, or always review? | Auto-merge **only** on an identical document SHA-256. Every other signal goes to the Review Queue — a wrongly merged receipt is expensive to unpick |
| 2 | Items sold by count rather than weight? | `unit = UN`; compute price-per-unit and leave €/kg `NULL` with an explicit reason. Never fabricate a weight |
| 3 | Is Fs per item or per receipt? | Per item, and always added by hand. There is no receipt-level toggle — an Fs article is a row the user appends, not a flag flipped on a printed line |
| 4 | Is there a `LoyaltyCard` table with an encrypted card number? | **No — removed.** The merchant already prints the loyalty number pre-masked on the till receipt (e.g. `"******4521"`); the pipeline never sees, and therefore never needs to encrypt, a full number. `LoyaltyAllocation.card_number_masked` stores exactly what was printed. A household's handful of cards do not need an inventory screen — "which cards have I used" is a `GROUP BY scheme_name, card_number_masked` over `LoyaltyAllocation`, not a CRUD entity |
| 5 | How many corrections before an alias is trusted? | Learn on the **first** confirmed correction — `confidence` starts low and rises with `correction_count`. Waiting for five corrections discards exactly the signal that gets us to 80% auto-accept; confidence, not a counter, gates auto-apply |
| 6 | Hand-written receipts? | Accepted, always routed to manual review — never auto-accepted |
| 7 | Multi-merchant / mall receipts? | Out of scope for v1. One `Receipt` = one payment transaction at one merchant |
| 8 | Does `ReceiptItem` carry its own `entity_id`? | Yes, denormalized from the parent. Redundant, but it keeps every analytics query single-table and matches the pattern every other module uses. The receipt stays the source of truth on re-attribution |
| 9 | What is the arithmetic tolerance? | €0.02 by default (brief §3), stored in `Setting` so a rounding-prone merchant can be widened without a deploy. **This file previously said €0.05 — that conflict is resolved in favour of the brief** |
| 10 | Where does the receipt↔transaction link live? | The shared `Link` table with `link_type = RECEIPT_TRANSACTION`. M1 never defines a ledger row |
| 11 | Is €/kg stored or derived? | **Derived** on `ReceiptItem` (deterministic from price and weight — the brief forbids storing what you can compute) and **persisted** on `ProductPriceHistory`, which is an immutable historical snapshot. Promote to a Postgres generated column only if sorting by €/kg becomes hot |
| 12 | Are the printed totals redundant with the item sums? | No. The printed values are independent extracted facts; the item sums are what we parsed. Reconciling the two **is** the arithmetic confidence signal, so both must be stored |
| 13 | May processing use a remote provider? | **Not by default, but the door stays open.** Every stage must have a local engine that works offline and unsubscribed — that is what makes the module usable today, with no subscription in hand. A remote engine may be registered alongside it and enabled per stage from `Setting`; without a credential the stage silently stays local. This is an enforced **default**, not an architectural ban: if a remote engine would materially raise the auto-accept rate, build the adapter, measure both against the same fixtures, and record the comparison |
| 14 | One parser for everything, or one per merchant? | **One per merchant, plus a generic fallback.** Layouts differ far more than they resemble each other, and a single parser regresses on merchant A whenever it is tuned for merchant B. Merchant detection therefore runs *before* extraction. A merchant with no profile is never blocked — it falls through to the generic parser with lower confidence |
| 15 | Is a product the same across pack sizes? | **Yes** — that is what makes €/kg comparable, and it is the household's own mental model. What varies between sizes is the **weight** and the merchant's article code, so `pack_variants` holds `{label, weight_kg, sku, barcode?}` per size. This replaces four fields with one |
| 16 | What happens to existing data when the category tree changes? | Rename costs nothing (rows reference ids). Reparent recomputes the **maintained ancestors** on affected rows in one audited transaction, so history is re-expressed under the new tree. Merge reassigns then soft-deletes. Retire is blocked while in use. The alternative — snapshotting the full triple per row — was rejected because it lets history drift from the live tree and silently mixes two taxonomies in one report |
| 17 | How do we know a category was actually checked? | `ReceiptItem.category_status` is `AUTO` until a human confirms it (`VALIDATED`) or assigns it directly (`MANUAL`). It is filterable everywhere, so "show me everything never checked" is one click, and the share validated is a quality metric in its own right |
| 18 | Where does category administration live — Core or M1? | The `Category` **entity** is Core §1a. The administration UI and the impact rules are M1's, scoped to `domain = GROCERY`, because M1 is the module that lives or dies by that tree. Other domains manage their own branches when they arrive |
| 19 | Does `Receipt` store the merchant's NIF? | **No — removed.** `Merchant.nif` already exists in Core, checksum-validated. The printed NIF's job is to *identify* the merchant during parsing — it is the strongest resolution key there is — and once `merchant_id` is set the NIF is reachable through it. Storing it again would create two sources of truth for one fact. A printed NIF that disagrees with the matched merchant is a **matching problem**, surfaced as a decision reason and sent to review, not a divergent value to persist on every receipt. The raw text remains in `raw_ocr_payload` for forensics |
| 20 | Is `subtotal_eur` stored? | **No — derived**, as `total_eur + total_discount_eur`. Two of the three printed figures determine the third, and `total_eur` (what was paid) plus `total_discount_eur` (which drives the proration ratio) are the two that carry independent weight. Storing the third buys a weak checksum that the far stronger item-level reconciliation already provides |
| 21 | Are `is_return` and `refund_item_count` needed? | **No — both removed and derived.** `refund_item_count` is `COUNT(quantity < 0)` and `is_return` is "every item is negative". Neither is printed on a receipt, so neither is an independent fact worth storing. Refunds still work exactly as before through negative quantities and `product_flag = REFUND`; nothing is lost but two columns that could drift out of step with the rows they summarise |
| 22 | Do Fs articles belong in `tags[]`? | **No.** `is_fs` is structural — it says the article was never on the invoice and is valued notionally; `tags[]` are open user labels with no effect on arithmetic. The household's own taxonomy file already draws this line, calling its context flags *"distintas da flag de exclusão Fs"*. An article can be `Fs` **and** tagged `#férias`; the two never substitute for each other |
| 23 | Does a receipt line carry a barcode or article code? | **Neither — confirmed against eight real fixtures.** A Portuguese *talão* prints only an IVA class letter, a truncated description and a value. No EAN, no SKU. Both were removed. The consequence is structural: `ProductAlias` and normalized fuzzy matching are the **only** way an item ever resolves, which makes them the load-bearing mechanism of the module rather than a nicety. `barcode` survives solely as an optional slot in `pack_variants` for the deferred scan-to-find flow |
| 24 | What is the fiscal QR actually worth? | Far more than validation. It encodes the issuer NIF, document date, gross total and VAT breakdown, making it the **highest-confidence anchor in the module**. The ATCUD is also printed as plain text (`ATCUD:JFP767JJ-035904`), so a QR that will not decode still yields the reference |
| 25 | How is size determined without a code? | By parsing the description, which is where the till puts it (`POLPA TOMATE GULOSO **500G**`, `SAL GROSSO CONTINENTE **1KG**`). `pack_variants` supplies the candidate weights and the parsed token picks between them |
| 26 | Is the IVA rate inferred? | **No — it is printed per line**, as a class letter whose meaning is merchant-specific: Continente `(A)`=6 % / `(C)`=23 %; Pingo Doce `C`=6 % / `E`=23 % / `I`=0 %. Inference is the fallback, not the rule, and sets `iva_inferred`. This removes a whole category of guesswork the spec previously assumed |
| 27 | Do receipts help with categorization? | **Yes, at no extra cost.** Both merchants group lines under their own headings (`Mercearia Salgada`, `FRUTAS E VEGETAIS`). Stored as `merchant_section` and fed to the classifier, this is a strong prior on a brand-new product — material for the ≥80 % target |
| 28 | Do all merchants treat discounts the same way? | **No, and they are opposite.** Continente's `SUBTOTAL` is already net of `POUPANCA`, with only the cartão subtracted (`40,56 − 4,00 = 36,56`); Pingo Doce's `TOTAL` is gross and `POUPANÇA` *is* subtracted (`15,70 − 0,50 = 15,20`). A single parser would silently overstate one household's spending. `field_hints.line_value_is_net` per profile — the sharpest justification for FR-1.16 |
| 29 | Which NIF is the merchant's? | The **organisational** one, decided by its first digit: `1`/`2`/`3` are natural persons, `5`/`6`/`8`/`9` are organisations. Continente prints its own `NIF: PT501591109` *and* the household's `NIF:PT209362367`; the leading `5` versus `2` separates them with no positional guessing. Header position is the tie-break when both are organisational |
| 30 | Points or euros? | **Euros.** `ACUMULOU NO SEU CARTAO 4,06€` and `Combustível ganho na compra: 0 EUR`. `LoyaltyAllocation` records `accrued_eur` and `discount_applied_eur`; there are no points. Continente's separate *selos* collectible scheme is out of scope |
| 31 | What exactly is an Fs item? | **An article that was never on the invoice**, appended to it by hand. Not a printed line reclassified — a row the household adds, classified like any paid product and carrying a notional value. This is why nothing about it is parsed, why it has no `line_no`, `merchant_section` or `iva_class_code`, and why it is excluded from the printed `item_count` check. It is also why adding one can never disturb a reconciliation that already passed: `paid_price_eur` is `0.00` and the printed totals are untouched. `notional_total_eur = total_eur + fs_value_eur` answers "what would this shop have cost had I paid for everything", and `fs_share_pct` measures Fs value **against what was paid** — €10 of Fs on a €10 invoice is `100 %`, not `50 %` |
| 32 | Is `is_fs` part of `product_flag`? | **No, it was split out.** Every `product_flag` value is read off the document; an Fs article has no document origin at all. Keeping `F` inside that enum conflated "what the receipt said" with "what the household added afterwards" — and forced a false exclusivity, since an appended article can still be a `SEASONAL` or `OTHER` line. A boolean beside the enum removes both problems |
| 33 | Do Fs estimates pollute price history? | **No — they are trusted and included.** An earlier draft excluded them from `ProductPriceHistory` on the grounds that a household estimate is not a merchant observation. That was over-cautious: the estimate is taken as correct, and the household would rather *choose* per query than have the decision made for it. So Fs rows are written like any other, carry `is_fs` onto the snapshot, and every price view respects the `fs` filter. The one guard that remains is arithmetic, not editorial: an Fs snapshot stores the notional value in **both** price columns, because writing the literal `paid_price_eur = 0.00` would pull every paid-price trend for that product toward zero |

---

## Source-of-Truth Mapping (legacy Excel → model)

The household's `SUPERMERCADOS_YYYY` sheets (1 row = 1 purchased article; ~1,275
rows in 2026) are the migration source. The sheet is **flat**: it has no
`Receipt` parent and derives the invoice total with `SUMIF` on `Full_Date`. On
import, **group rows by `Full_Date` + store into a `Receipt`**, then map each
row to a `ReceiptItem`.

| Legacy column | Model target | Notes |
| :--- | :--- | :--- |
| `Full_Date` (`Date` + `Hora`) | `Receipt.purchased_at` + `purchase_date`, and the grouping key | Rows sharing a `Full_Date` form one `Receipt`. Keep the Lisbon calendar date |
| `Date_ID` | *derived* | `YYYYMMDD`; compute, never store |
| `Supermercado` | `Receipt.merchant_id` | Find-or-create the merchant from the distinct values (Continente, Pingo Doce, Auchan, …) |
| `Descrição` | `ReceiptItem.description_raw` → `description_norm` | Feeds fuzzy → `MasterProduct` resolution |
| `Price` | `unit_price_pvp_eur` | Gross list price before discounts |
| `PromoInd` | `promo_discount_eur` | Per-item promo (32.8% filled) |
| `PromoGlob` | `invoice_allocated_discount_eur` | Populated on only ~9% of legacy rows — **recompute deterministically** from the receipt-level ratio for every row |
| `Price_Final` | `paid_price_eur` | Primary net-spend metric; verify against the recomputed value and report drift |
| `Categoria` / `_2` / `_3` | `category_l1_id` / `l2` / `l3` | Legacy is very incomplete (41% / 37% / 21%) — this gap *is* the auto-categorization backlog |
| `Peso` | `weight_observed_kg` | Real scale weight (43.8% filled) |
| `Peso (proposta)` | `weight_listed_kg` ← `MasterProduct.pack_variants` | The legacy `VLOOKUP`-by-description is exactly the curated-weight learning (93% filled) |
| `Preco/Kg/real` | *derived* `price_per_kg_pvp_eur` | Legacy name is a misnomer: it is `Price / Peso`, i.e. the **list** price per kg |
| `Preco/Kg/promo` | *derived* `price_per_kg_promo_eur` | `(Price − PromoInd) / Peso` |
| `Flags` (`F`) | `is_fs = true` | These rows were never on an invoice — they import as appended Fs articles with the sheet's price as `unit_price_pvp_eur`, `notional_value_source = MANUAL` and `paid_price_eur = 0.00`. The legacy `SUMIF(Flags,"F")` total becomes the derived `fs_value_eur` |
| `Preço Fatura` (`SUMIF` per `Full_Date`) | `Receipt.total_eur` | Becomes an explicit parent field, not a per-row formula |
| `Notas` | `ReceiptItem.notes` | Empty today; preserve the field |
| `Status` | `Receipt.status` / item `confidence` | Empty today; drives the Review Queue going forward |
| `ID` | `ReceiptItem.legacy_row_ref` | **Not** the primary key — PKs are UUID v7. Kept solely for traceability back to the spreadsheet |

**Caveats carried over:** categories are mostly blank — do not assume
completeness; `Peso` and €/kg exist for only part of the rows; `PromoGlob` was
computed on ~9% of rows, so the import must recompute it consistently. The
import is idempotent: re-running it updates rather than duplicates.

---

## Integration Contract
- **Exposes:** `Receipt`, `ReceiptItem`, `MasterProduct`, `ProductPriceHistory`, `LoyaltyAllocation`; category spend, Fs analytics and price trends to Dashboards (M8).
- **Consumes (all defined in the orchestrator brief §1a, never redefined here):** `Entity` — attribution and RBAC; `Merchant` — receipt issuer and parser-profile key; `Category` — the taxonomy this module administers for the `GROCERY` domain; `Tag`; `Document` — original invoice storage and SHA-256 duplicate detection; `Link` — `RECEIPT_TRANSACTION` edges; `ReviewTask` — the shared Review Queue this module first populates; `Setting` — confidence thresholds and arithmetic tolerance; `AuditLog`; `ImportBatch` and `ProcessingJob` — every upload and the legacy migration. Plus `Transaction` (M2) for ledger reconciliation, which is optional and degrades cleanly when the ledger does not yet exist.
- **Reconciles with:** Banking (M2) via merchant + date (±3 days, configurable) + amount tolerance, emitting `Link(RECEIPT_TRANSACTION)` edges carrying confidence and decision reasons.
- **Guarantees:** the module is fully functional with **no subscription and no network** — every stage has a local engine, and a remote one is contacted only when explicitly configured; money is decimal EUR everywhere; `paid_price_eur` is always what was actually paid; `ProductPriceHistory` is append-only; a category is never silently orphaned by a tree edit.
