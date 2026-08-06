# Module 1 — Supermarket & Receipt Processing (`modules/receipts`)

## Purpose
Ingest supermarket invoices (PDF/image/manual), identify and normalize every product, categorize it into a 3-tier hierarchy, track consumption trends and price evolution, and automate duplicate detection, shrinkflation alerts, and per-item VAT inference for accurate household spending visibility.

## Actors & User Stories
- *As a household shopper*, I photograph a receipt; the system extracts products, weights, prices, and discounts without manual entry.
- *As a budget reviewer*, I see only flagged line items (low OCR confidence, weight mismatches, or new products) and confirm or correct them in under 10 seconds each.
- *As a price analyst*, I track €/kg evolution across merchants and seasons for products I buy frequently, and receive shrinkflation alerts when the same product is lighter but costs the same.
- *As a wellness member*, I filter receipts by dietary tags (organic, vegan, gluten-free) and allergen flags to monitor specialized spending.
- *As a household maintainer*, I CRUD the merchant list, master product database, allergen/dietary tags, and curated weights per product.
- *As a compliance reviewer*, I verify receipt ATCUD (Portuguese tax stamp) validity and loyalty card allocations for Fs reconciliation.

## Data Model
All monetary fields (`_eur` suffix) are `NUMERIC(10,2)` decimal EUR amounts (e.g. `19.99`), never minor-unit integers; UI displays them pt-PT-formatted (e.g. `19,99€`).
- **Receipt**: `id, entity_id, merchant_id, purchased_at (timestamptz, local date+time), document_id, nif_merchant (varchar, Portuguese merchant tax ID), loyalty_card_id?, loyalty_points_allocated, subtotal_eur (NUMERIC(10,2)), total_eur, total_discount_eur, fs_total_eur, fs_item_count, item_count, refund_item_count, is_return, status, confidence, decision_reasons (JSONB), raw_ocr_payload (JSONB), atcud_qr_code, atcud_valid (bool), parsed_payment_methods (JSONB array: {method: CASH|CARD|LOYALTY, amount_eur}), tags[], created_at, updated_at`.
- **ReceiptItem**: `id, receipt_id, line_no, purchased_at, description_raw, description_norm, sku, barcode, master_product_id, category_l1_id, category_l2_id, category_l3_id, quantity (NUMERIC(14,4)), unit (enum: kg|g|L|mL|un|pack), weight_listed_kg (curated/proposed via description lookup), weight_observed_kg (real, register scale), is_bulk_weighed, unit_price_pvp_eur (PVP list price = legacy “Price”, gross before any discount), promo_discount_eur (per-item promo = legacy “PromoInd”), promo_type (enum: ABSOLUTE|PERCENTAGE|BOGO|LOYALTY_POINTS), invoice_allocated_discount_eur (invoice/loyalty discount prorated across items = legacy “PromoGlob”; proration = (unit_price_pvp - promo_discount) × invoice_discount_ratio), paid_price_eur (net final = legacy “Price_Final” = pvp - promo - invoice_allocated), price_per_kg_pvp_eur (“Preco/Kg/real” = pvp/weight), price_per_kg_promo_eur (“Preco/Kg/promo” = (pvp - promo)/weight, after individual promo only), price_per_kg_final_eur (paid/weight, after all discounts), iva_rate (enum: 6|13|23, inferred), iva_eur (inferred), product_flag (enum: F|REFUND|DEPOSIT_RETURN|SEASONAL|other; “F” is the legacy flag summed into fs_total_eur), dietary_tags (JSON array: ORGANIC|VEGAN|GLUTENFREE|...), allergen_flags (JSON array), margin_signal (float, for shrinkflation scoring), is_duplicate_of_item_id?, notes (legacy “Notas”, free text), confidence, decision_reasons (JSONB), created_at, updated_at`.
- **MasterProduct**: `id, canonical_name, brand, barcode, sku_reference, default_category_l1_id, default_category_l2_id, default_category_l3_id, curated_weights (NUMERIC(14,4)[] array, kg), curated_isoweight_equivalents (JSON), aliases (JSON array of {merchant, description}), dietary_attributes (ORGANIC|VEGAN|GLUTEN_FREE|...), allergen_list (JSON array), seasonal_flags (SPRING|SUMMER|AUTUMN|WINTER), expected_shelf_life_days, deposit_value_eur (for bottles/packaging refunds), is_deleted, created_at, updated_at`. **User-managed.** Two products with different categories are, by rule, **different master products**.
- **ProductPriceHistory** (derived, append-only): `id, master_product_id, merchant_id, observed_at (date), price_per_kg_pvp_eur, price_per_kg_paid_eur, source_receipt_item_id, weight_kg, list_price_eur, shrinkflation_indicator (bool: weight fell but price static/up), created_at`.
- **ProductAlias** (user-curated, learned): `id, master_product_id, merchant_id, merchant_description (raw text from that merchant's receipts), confidence (0–1, learned from user corrections), last_used_at`.
- **ReceiptDuplicateLog**: `id, original_receipt_id, potential_dup_receipt_id, merchant_id, merchant_date, amount_eur, detection_method (HASH|MERCHANT_DATE_AMOUNT|OCR_MATCH), similarity_score (0–1), status (CONFIRMED|DISMISSED), reviewed_at, reviewed_by`.
- **LoyaltyAllocation**: `id, receipt_id, loyalty_scheme_name, points_awarded, discount_applied_eur, invoice_allocated_discount_eur, allocation_method (PROPORTIONAL|ITEM_LEVEL), applied_to_item_ids (BIGINT[] array), created_at`.

## Category Taxonomy (pt-PT) — semantics, normalization & seed

- **Language policy.** Category schema/columns and `code`/slug identifiers are **English**; the **display names are Portuguese (pt-PT)**, authored exactly as the household presented them. UI is pt-PT-first (i18n-ready). Store each category as `(code_en, display_name_pt, level, parent_id, domain)`.
- **What each level means.** **L1** = macro group (`Aperitivos`), **L2** = subcategoria (`Batatas Fritas`), **L3** = **normalized product-genus** (`Batata Frita Ondulada`) — brand-, size- and SKU-agnostic.
- **L3 is a category, NOT the product.** The brand + variant + package live on `MasterProduct`, which references `(L1,L2,L3)`. Example: `Batata Frita Continente` is **not** an L3 — it is a `MasterProduct` with `L3 = Batata Frita Lisa`, `brand = Continente`. This keeps L3 useful (compare €/kg across brands of the same genus) without losing SKU granularity (which lives on `MasterProduct`).
- **Brand-as-L2 exception.** Where the household tracks premium by brand (e.g. `Gelados`, `Pastilhas`), L2 = brand is a deliberate exception (L2 = brand, L3 = linha/sabor, `MasterProduct` = exact SKU). Flag those L2 nodes with `brand_axis = true`.
- **Empty L3 arrays** are valid placeholder L2 nodes (L3 is optional).
- **Seed source (authoritative vocabulary):** [seed/supermarket-categories.pt-PT.json](../seed/supermarket-categories.pt-PT.json). The build imports this to seed the tree; its `review_candidates` list documents normalization decisions (accents/casing fixes, EN→pt-PT L1 renames `Gym→Ginásio`/`Misc→Diversos`/`Others→Outros`, merged/duplicate nodes, removed garbage tokens). Different category ⇒ different master product.

## Functional Requirements
- **FR-1.1 (OCR Ingestion):** Parse uploaded receipt PDFs/images via `pdfplumber` (digital) or Tesseract (scans) to extract: merchant, date/time, all line items, quantity/weight (with unit), unit price (PVP), promotions, discounts, totals, and payment method breakdown. Capture raw OCR payload and per-field confidence scores.
- **FR-1.2 (Manual Fallback & Editing):** Full create/edit of receipts and line items; edits trigger recomputation of totals, per-item VAT, price-per-kg, and Fs reconciliation. Soft-delete old versions; track correction history for model feedback.
- **FR-1.3 (Hierarchical Categorization — pt-PT):** 3-tier taxonomy with **pt-PT display names** and English `code`/schema. **L3 = normalized product-genus** (brand/size/SKU-agnostic), *not* the purchased item — brand/variant/package live on `MasterProduct`, which references `(L1,L2,L3)`. Brand-as-L2 is an accepted exception for premium-by-brand ramos (`Gelados`, `Pastilhas`), flagged `brand_axis=true`. Seed vocabulary: [seed/supermarket-categories.pt-PT.json](../seed/supermarket-categories.pt-PT.json). **Immutable rule: different category = different master product.** Categorization auto-suggested from master product, overridable with feedback loop.
- **FR-1.4 (Price Evolution & Shrinkflation Detection):** Maintain `ProductPriceHistory`; compute `margin_signal` (weight change vs price change); render trend lines for €/kg PVP and €/kg Paid; alert on shrinkflation (weight ↓ or unit count ↓, price → or ↑).
- **FR-1.5 (Contextual Flags & Tags):** Support receipt-level and item-level tags (`#vacation`, `#special_event`, `#kids`, `#organic`, `#bulk_buy`) distinct from `product_flag`. Dietary/allergen attributes queryable per item.
- **FR-1.6 (Document Storage & ATCUD Validation):** Store original PDF/image; extract and validate Portuguese ATCUD (QR-code tax stamp); flag invalid/missing ATCUD. Linked via `Document` entity with SHA-256 content addressing for deduplication.
- **FR-1.7 (Merchant Management & NIF Validation):** Full CRUD UI for merchants; validate Portuguese NIF (9-digit tax ID); track aliases and category defaults. Receipts only reference existing merchants.
- **FR-1.8 (Fuzzy Product Normalization):** Resolve merchant-specific descriptions to `MasterProduct` using similarity (Levenshtein/token-set) + learned `ProductAlias` mappings. Feedback loop: user corrections update alias confidence and retrain.
- **FR-1.9 (Receipt Duplicate Detection):** Auto-detect potential duplicates via document hash (SHA-256), merchant+date+amount triangulation (±3 min, ±0.10 EUR), and OCR payload similarity. Flag for manual review; allow confirmation to merge/void duplicates.
- **FR-1.10 (Multi-Payment Methods & Loyalty Allocation):** Parse composite payment methods (e.g., cash + loyalty card, card + store credit). Track loyalty card number (masked); allocate cartão discount across items proportionally or per-item, separated from promo discounts. Fs items get proportional allocation but excluded from totals.
- **FR-1.11 (Per-Item VAT/IVA Inference & Validation):** Infer Portuguese IVA rate (6% food, 13% reduced, 23% standard) per item from category and item description; validate sum against invoice totals; highlight discrepancies for review.
- **FR-1.12 (Deposit & Refund Handling):** Model bottle deposits (tara) and packaging refunds as `product_flag: DEPOSIT_RETURN`; link to original purchase; track refund status (PENDING|CREDITED). Refund items carry negative quantities and are excluded from regular totals.
- **FR-1.13 (Bulk Weigh & Unit Price Ambiguity):** Distinguish listed weight (label) vs. observed weight (register scale); handle items without upfront prices (weighed at checkout). Flag for confidence review if weight is missing for €/kg calculation.

## Automation Rules
- Merchant resolved by name/alias fuzzy match (≥0.80 confidence) or manual selection; OCR text confidence per field captured.
- Product resolved to `MasterProduct` by barcode (highest priority), SKU, alias match, then description similarity + category hint.
- Line-item confidence combines: OCR text confidence (per field), merchant+product match score, weight validity (curated list), arithmetic consistency (Σ items ≈ totals ± tolerance), and IVA rate reasonableness.
- **Fs flag rule (CRITICAL):** Items with `product_flag == "Fs"` are **entirely excluded from `total_eur`** and **included only in `fs_total_eur`/`fs_item_count`**. Arithmetic validation must enforce: `Σ(non-Fs items) == (total_eur - discounts)` and `Σ(Fs items) == fs_total_eur`. Violation → auto-flag for review.
- Loyalty discount allocation: when `loyalty_points_allocated` > 0, split proportionally across `invoice_allocated_discount_eur` per item; Fs items receive allocation but sums excluded from receipt total.
- Shrinkflation signal: if a product's weight falls ≥5% relative to the last 3 months' average but unit price holds or increases, increment `margin_signal` and alert.
- Duplicate detection threshold: document hash exact match → immediate merge prompt; merchant+date+amount within ±3 min / ±0.10 EUR and OCR similarity ≥0.95 → `NEEDS_REVIEW`.

## UI / Screens
1. **Receipt Upload & Processing**: drag-drop or camera, progress bar, auto-preview extracted data.
2. **Receipt Review Screen**: side-by-side original image + parsed grid; uncertain fields highlighted in yellow; one-click confirm/edit; inline MasterProduct picker; suggested category and allergen tags.
3. **Receipts List/Dashboard**: filterable by merchant, date range, tag, category, Fs/non-Fs split; summary cards (total spend, Fs split, item count).
4. **Duplicate Detection Modal**: flagged potential duplicates (original + suspect) with similarity score; merge/dismiss actions.
5. **Merchant Manager**: CRUD, NIF validation, category defaults, logo upload.
6. **Master Product Manager**: CRUD, barcode/SKU, curated weights (multi-select), aliases per merchant (add/remove with confidence), dietary/allergen checkboxes, seasonal flags.
7. **Price Evolution Chart**: product selector, price-per-kg (PVP/Paid) trend by merchant, shrinkflation overlay, export CSV.
8. **Loyalty Card Management**: card number (masked), associated receipts, total points/discount, per-receipt allocation breakdown.

## API Surface
- `POST /receipts` (multipart: file + metadata, idempotent via Idempotency-Key)
- `GET /receipts` (filters: merchant, date range, tag, category, Fs, status, entity_id)
- `GET /receipts/{id}` (includes raw payload, confidence breakdown, links)
- `PATCH /receipts/{id}` (edit metadata, items, tags; recomputes totals)
- `POST /receipts/{id}/confirm` (transitions to CONFIRMED; feedback to product/merchant models)
- `POST /receipts/{id}/check-duplicates` (on-demand re-scan)
- `POST /receipts/{id}/merge-duplicate/{dup_id}` (void one, link items to original)
- `GET /receipts/{id}/loyalty-allocation` (breakdown per item)
- `GET/POST/PATCH/DELETE /merchants` (full CRUD, NIF validation)
- `GET/POST/PATCH/DELETE /master-products` (full CRUD, aliases, weights, allergens)
- `POST /master-products/{id}/merge` (deduplicate master records)
- `POST /product-aliases/learn` (update ProductAlias confidence from user correction)
- `GET /products/{id}/price-history` (with shrinkflation signals)
- `GET /receipts/analytics/shrinkflation` (products flagged, date range)
- `GET /receipts/analytics/category-spend` (by L1/L2/L3, Fs breakdown, tags)

## Analytics & KPIs
- Price-per-kg evolution (PVP and Paid) per product/merchant, including seasonal variance.
- Shrinkflation detection: products with weight ↓ or unit count ↓ vs. previous 12 months.
- Loyalty savings: cumulative discount via loyalty cards per receipt, per card, per scheme.
- Fs budget tracking: total Fs spend, Fs item count, Fs as % of household budget.
- Basket composition: category split, dietary preference breakdown, organic % of total spend.
- Promotion ROI: discount rate by type (BOGO, percentage, absolute, loyalty), effectiveness by merchant.
- Duplicate receipts: % flagged and resolved, savings from merge operations.
- OCR quality: % of auto-accepted receipts, mean confidence, per-field accuracy on validation sample.

## Edge Cases & Validation
- **Reconciliation tolerance:** Σ(non-Fs items with discounts) must equal `total_eur ± 0.05 EUR` (rounding tolerance). Fs items excluded from this check.
- **Multi-weight units:** kg-priced items vs. unit-priced items handled separately. Items with both quantity and weight (e.g., 3 packs × 250g) support both.
- **Missing prices:** Bulk weigh items (no upfront price) flagged for manual entry or excluded from price-per-kg until weight confirmed.
- **OCR garbling:** Thermal receipts often corrupt special characters (€, ü, ç). Fuzzy matching tolerates ±1 character substitution; if unrecoverable, flag low confidence.
- **Refunds & returns:** Negative line items (`quantity < 0`) treated as refunds; never summed into `item_count`; separate `refund_item_count` tracked. Refund receipts may link to original purchases.
- **Deposits (tara):** Bottle deposits are separate `product_flag: DEPOSIT_RETURN` items; must never be categorized as groceries; reconciled when refund credited.
- **Payment method ambiguity:** If receipt shows "DINHEIRO + CARTÃO" (cash + card) but no split amounts, prompt user for allocation.
- **Missing ATCUD or NIF:** Flag for review; warn user of tax compliance implications (Portugal requires ATCUD on digital invoices).
- **IVA cross-check:** If per-item IVA sum ≠ invoice total IVA within ±0.01 EUR, mark receipt `needs_review`.

## Additional / Enriched Requirements
1. **Barcode/QR-Code Extraction & EAN Validation (NEW):** Extract EAN-13 barcodes; use EAN checksum validation; Portuguese ATCUD QR contains invoice metadata — validate digital signature if available. Optional external product-database enrichment (privacy-aware, opt-in).
2. **Shrinkflation & Margin Tracking (NEW):** Compute `margin_signal = (current_weight / avg_weight_12m) - (current_price / avg_price_12m)`; alert when ratio < 0.95.
3. **Dietary & Allergen Tagging (NEW):** Store allergen list per `MasterProduct`; index for quick filtering; optional external allergen database (opt-in).
4. **Seasonal Produce Flagging (NEW):** Tag seasonal availability; highlight out-of-season buys for price anomaly investigation.
5. **Loyalty Scheme Reconciliation (NEW):** Multiple loyalty cards per household (Continente, Pingo Doce, El Corte Inglés); track points accrued/redeemed; flag mismatches.
6. **Weight Unit Standardization (NEW):** Normalize kg/g/L/mL/un/pack to a standard unit for cross-unit price comparison.
7. **SKU & Batch/Lot Tracking (NEW):** Capture SKU and lot/batch when available for recall alerts and per-batch price variance.
8. **Return Window & Freshness Alerts (NEW):** Store expected shelf life; alert as return window approaches (14–30 days typical in Portugal).
9. **Bulk vs. Retail Price Comparison (NEW):** Flag surprising retail-cheaper-than-bulk cases (potential data entry error).
10. **Payment Method Tracking (NEW):** Track CASH/DEBIT/CREDIT/LOYALTY/STORE_CREDIT in composite payments; aggregate preference over time.

## Open Questions / Decisions
1. **Auto-merge high-confidence duplicates or always review?** → *Auto-merge if confidence ≥ 0.99 and document hashes identical; otherwise review.*
2. **Weight-agnostic bulk items (sold by count)?** → *Allow `unit = "un"`; compute price-per-unit, skip €/kg with explanation.*
3. **Fs allocation per-item or whole-receipt?** → *Per-item flag takes precedence; receipt-level Fs is an optional override when all items are Fs.*
4. **Loyalty card number storage?** → *Encrypt with app-level key; mask in UI (last 4 visible); exclude from exports unless explicitly requested.*
5. **Corrections before retraining an alias?** → *5+ corrections per alias; explicit "learn" action per correction; human review before deployment.*
6. **Hand-written receipts?** → *Support both; hand-written flagged for manual review (lower OCR confidence).*
7. **Multi-merchant/mall receipts — one Receipt or many?** → *One Receipt per payment transaction; ReceiptItem may override `merchant_id`; aggregated totals must reconcile.*

## Definition of Done
- All FRs (1.1–1.13) implemented with unit + integration tests (≥85% coverage on domain/services).
- ≥80% of uploaded receipts auto-accepted without user edits on the seed sample (Continente, Pingo Doce, Auchan).
- Merchant CRUD + NIF validation live; Product CRUD + alias management live; Price history + shrinkflation chart render.
- Fs rule proven by unit tests: non-Fs sum = `total_eur ± tolerance`, Fs sum = `fs_total_eur`.
- Duplicate detection tested on sample pairs (targets: ≥95% TPR, ≤2% FPR).
- Loyalty allocation correctly splits discount across items; Fs items receive allocation but excluded from receipt totals.
- OCR confidence per field + per-item; `decision_reasons` JSONB populated and displayed in UI.
- Playwright e2e: upload → review → confirm → price chart.
- Portuguese IVA inference cross-checked against invoice totals ≤ ±0.01 EUR.
- ATCUD validation integrated (digital signature check optional).

## Integration Contract
- **Exposes:** `Receipt`, `ReceiptItem`, `MasterProduct`, `ProductPriceHistory`, `Document`, `LoyaltyAllocation`; linked via `Link RECONCILES receipt↔transaction` to Banking (M2).
- **Consumes:** `Merchant`, `Category`, `Tag`, `Entity`, `Document` from Core; optionally external `OcrProvider`/`ExtractionProvider` (privacy-aware, opt-in).
- **Reconciles-with:** Banking (M2) via merchant + date (±3 days) + amount tolerance; feeds Dashboards with category spend, Fs analytics, price trends.

## Source-of-Truth Mapping (legacy Excel → model)
The household's current `SUPERMERCADOS_YYYY` sheets (1 row = 1 purchased article; ~1,275 rows in 2026) are the migration source. The legacy sheet is **flat**: it has no `Receipt` parent and derives the invoice total with `SUMIF` on `Full_Date`. On import, **group rows by `Full_Date` (+ store) into a `Receipt`**, then map each row to a `ReceiptItem`.

| Legacy column | Model target | Notes |
|---|---|---|
| `Full_Date` (`Date`+`Hora`) | `Receipt.purchased_at` + item grouping key | Rows sharing one `Full_Date` = one `Receipt`. |
| `Date_ID` | *derived* | `YYYYMMDD`; compute, don't store. |
| `Supermercado` (Pingo Doce, Continente) | `Receipt.merchant_id` | Seed the merchant list from distinct values. |
| `Descrição` | `ReceiptItem.description_raw` (+ `description_norm`) | Feeds fuzzy → `MasterProduct` resolution. |
| `Price` | `unit_price_pvp_eur` | Gross/official price before discounts (PVP). |
| `PromoInd` | `promo_discount_eur` | Per-item promo (32.8% filled). |
| `PromoGlob` | `invoice_allocated_discount_eur` | Invoice-level discount **prorated** across items: `(Price - PromoInd) × ratio`. Only populated on some rows in legacy — recompute deterministically. |
| `Price_Final` (`Price - PromoInd - PromoGlob`) | `paid_price_eur` | Primary net-spend metric. |
| `Categoria` / `Categoria_2` / `Categoria_3` | `category_l1_id` / `l2` / `l3` | 3-tier. Legacy is **very incomplete** (41% / 37% / 21%) — exactly the auto-categorization backlog this module targets. |
| `Peso` | `weight_observed_kg` | Real weight for €/kg (43.8% filled). |
| `Peso (proposta)` | `weight_listed_kg` ← `MasterProduct.curated_weights` | Legacy `VLOOKUP`-by-description = the curated-weight learning (93% filled). |
| `Preco/Kg/real` | `price_per_kg_pvp_eur` | `Price / Peso`. |
| `Preco/Kg/promo` | `price_per_kg_promo_eur` | `(Price - PromoInd) / Peso` (after individual promo only). |
| `Flags` (`F`) | `product_flag = F` | Summed into `fs_total_eur` / `fs_item_count`; **excluded from `total_eur`**. `SUMIF(Flags,"F")` in legacy = the Fs total. |
| `Preço Fatura` (`SUMIF` per `Full_Date`) | `Receipt.total_eur` | Becomes an explicit parent field, not a per-row formula. |
| `Notas` | `ReceiptItem.notes` | Empty today; preserve the field. |
| `Status` | `Receipt.status` / item `confidence` | Empty today; drives the Review Queue going forward. |
| `ID` | `ReceiptItem.id` | Internal identifier. |

**Caveats carried over:** categories are mostly blank (don't assume completeness); `Peso`/€/kg exist only for part of the rows; `PromoGlob` was computed on only ~9% of rows — the import must (re)compute it consistently from the receipt-level discount ratio.
