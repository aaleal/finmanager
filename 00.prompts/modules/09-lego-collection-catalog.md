# Module 9 — LEGO Collection Catalog

## 1. Purpose and Scope
Catalog the household's LEGO sets as trackable household assets. The module
distinguishes the **catalog identity** of a set (its official metadata, shared
by every copy owned) from each **physical copy** owned (its own acquisition
cost, storage location, build state, completeness, physical condition, and
ownership lifecycle), so a user can see both "how many copies of set X do I
own" and the individual history of each copy. All monetary fields are tracked
in EUR only. It provides collection analytics and exposes the collection's
aggregate current value to the net-worth module.

Because selling an individual set is uncommon, performance metrics (ROI,
appreciation) are based on **unrealized** gains — current market value versus
acquisition cost — not on realized sale proceeds. Sale price and date are
recorded for history when a copy is sold, but do not drive the headline
ROI/appreciation KPIs.

The current scope is strictly limited to LEGO sets. Future support for other
collectible types must not influence the initial domain model or user interface.

## Actors 

### Primary Actor
A person who owns a LEGO collection and wants to manage inventory, monitor value, understand financial performance, track storage locations, and support buying/selling decisions.

## User Stories

### US01. Collection Registration
As a user, I want to add a LEGO set by its `set number` so the system can retrieve
the available metadata from configured sources so I can reduce manual data entry while retaining control over the stored information.

### US02. Collection Tracking
As a user, I want to maintain accurate information about each physical copy I
own, including its build state, completeness, physical condition, storage
location, and ownership lifecycle status, so I always know what I own, how
many copies of each set I have, where each copy is, and whether it remains
part of my active collection.

**Examples:**
- Build state (e.g. sealed, built, disassembled)
- Completeness (independent of build state)
- Physical condition (independent of build state and completeness)
- Ownership lifecycle status
- Storage location
- Acquisition date and cost
- Notes

### US03. Collection Search
As a user, I want to quickly find any set in my collection and view its key information.

**Examples**
- search by set number
- search by name
- search by theme
- search by location
- search by status

### US04. Valuation & Performance
As a user, I want the system to continuously track the market value of my collection so I can understand appreciation and investment performance based on unrealized gains, since selling individual sets is uncommon.
**Metrics:**
- Latest available market value
- Unrealized gain / loss
- Appreciation %
- ROI % — always computed from unrealized gains (current market value vs. acquisition cost), never from a sale price
- Value evolution over time
- Realized sale price/date — recorded per copy for history, shown separately, and excluded from the ROI/appreciation KPIs

### US05. Collection Analytics
As a user, I want to see aggregated statistics about the composition, value,
condition, completeness, and storage distribution of my collection so I can
identify trends and make informed collection-management decisions.

### US06. Market Monitoring
As a user, I want quick access to relevant external marketplaces and valuation
sources, such as BrickLink, and the option to request valuation updates from
configured providers, so I can make informed buying and selling decisions.

### US07. Visual Catalog Management
As a user, I want to associate one or more images with each LEGO set and select
a primary image so I can browse and identify my collection visually.

### US08. Household Asset Integration
As a user, I want the aggregate latest available value of my active LEGO
collection to be included in my household asset portfolio so I can understand
its contribution to net worth.

### US09. Set Grouping & Copy Count
As a user, I want to see, for any given set, how many physical copies I own
and the individual details of each copy, so I can tell duplicates apart
without losing track of each copy's own condition, storage, and value.

## Data Model

### Entities & Attributes

All monetary attributes are denominated in **EUR only** (no multi-currency, no
FX conversion). Values are stored as `NUMERIC(10,2)` decimal EUR amounts (e.g.
`19.99`, up to ~99,999,999.99), never integer minor units, matching the convention used across the
rest of the application (see Module 2, Module 6); UI displays them pt-PT-formatted
(e.g. `19,99€`).

**Definition — in-scope instance.** Unless stated otherwise, every KPI, aggregate,
and net-worth contribution in this module operates over *in-scope* `LegoSetInstance`
rows: `is_active = true` AND `ownership_status IN (IN_COLLECTION, LISTED_FOR_SALE)`.
This is distinct from `is_active` alone, which is only a soft-delete flag — a `SOLD`
instance can remain `is_active = true` (kept for history) while being out of scope
for value/ROI KPIs and net worth.

The catalog identity of a set (`LegoSetModel`) is separated from each physical
copy owned (`LegoSetInstance`). This lets a user see how many copies of a
given set they own, while each copy still carries its own cost, storage,
build state, completeness, physical condition, and ownership lifecycle.

#### 1. `LegoSetModel` (Catalog / Reference Entity)
Represents the *identity* of a LEGO set (or a custom/MOC build) — the metadata
shared by every physical copy owned of that set. One row exists per unique
`set_number` (or per custom build) within an entity's scope; multiple owned
copies reference the same `LegoSetModel` row via `LegoSetInstance`.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `entity_id` | `UUID` | Household / User isolation scope |
| `set_number` | `String?` | Official LEGO set number (e.g., `"10307"`, `"75192"`); `NULL` for custom/MOC builds |
| `is_custom` | `Boolean` | `true` for a custom/MOC build with no official set number (`default: false`) |
| `name` | `String` | Set name (auto-populated via lookup or manually entered) |
| `theme` | `String?` | Primary theme (e.g., `"Icons"`, `"Star Wars"`, `"Technic"`) |
| `subtheme` | `String?` | Optional subtheme (e.g., `"Ultimate Collector Series"`) |
| `release_year` | `Integer?` | Year the set was officially released |
| `retired_year` | `Integer?` | Year the set was officially retired (`NULL` if active/available) |
| `piece_count` | `Integer?` | Total number of pieces in the set |
| `minifig_count` | `Integer?` | Total number of minifigures included |
| `short_description` | `String?` | Concise 1-sentence summary of the set |
| `is_active` | `Boolean` | Soft-delete / active status flag (`default: true`) |
| `created_at` | `Timestamp` | Record creation timestamp |
| `updated_at` | `Timestamp` | Record last updated timestamp |

Unique constraint: `(entity_id, set_number)` when `set_number IS NOT NULL`.

---

#### 2. `LegoSetInstance` (Owned Physical Copy)
Represents exactly **one** physical copy owned by the household. Each copy is
always its own row — there is no `quantity` field; owning three copies of the
same set means three `LegoSetInstance` rows referencing the same
`LegoSetModel`.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `entity_id` | `UUID` | Household / User isolation scope |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `acquisition_date` | `Date?` | Date the copy was acquired |
| `acquisition_cost_eur` | `NUMERIC(10,2)` | Actual purchase price paid, EUR (*custo real*) |
| `acquisition_source` | `Enum` | `RETAIL` \| `SECONDHAND` \| `GIFT` \| `OTHER` |
| `acquisition_merchant_id` | `UUID?` | Optional reference to merchant entity |
| `acquisition_transaction_id`| `UUID?` | Optional link to banking ledger transaction (Module 2) |
| `storage_location_id` | `UUID?` | Foreign key to `StorageLocation` |
| `build_state` | `Enum` | `SEALED` \| `BUILT` \| `PARTIALLY_BUILT` \| `DISASSEMBLED` — whether the copy is currently assembled |
| `completeness_status` | `Enum` | `COMPLETE` \| `MISSING_PARTS` \| `UNKNOWN` — independent of build state (e.g. a `BUILT` set can be `MISSING_PARTS`). A `SEALED` + `MISSING_PARTS` combination is unusual but valid (e.g. a factory packaging shortage identified from a community parts-count report without opening the box) — not a data-entry error. |
| `physical_condition` | `Enum` | `MINT` \| `GOOD` \| `WORN` \| `DAMAGED` — physical wear of box/pieces, independent of build state and completeness |
| `has_box` | `Boolean` | Indicates if original box is present (`default: true`) |
| `has_instructions` | `Boolean` | Indicates if instruction booklet is present (`default: true`) |
| `ownership_status` | `Enum` | `IN_COLLECTION` \| `LISTED_FOR_SALE` \| `SOLD` \| `GIFTED_AWAY` \| `DONATED` \| `LOST_OR_DAMAGED` \| `DISPOSED` — ownership lifecycle (`default: IN_COLLECTION`) |
| `sale_price_eur` | `NUMERIC(10,2)?` | Actual sale price received, EUR; set only when `ownership_status = SOLD` |
| `sale_date` | `Date?` | Date the copy was sold; set only when `ownership_status = SOLD` |
| `short_description` | `String?` | Concise 1-sentence summary specific to this copy (optional override) |
| `notes` | `Text?` | Free-text notes (e.g., box wear, missing piece list) |
| `is_active` | `Boolean` | Soft-delete / record status flag, independent of `ownership_status` (`default: true`) |
| `created_at` | `Timestamp` | Record creation timestamp |
| `updated_at` | `Timestamp` | Record last updated timestamp |

---

#### 3. `LegoValuation` (Market Price History)
Immutable, append-only records tracking current market value (*custo atual*)
over time. Valuations apply to the **set model** (the market doesn't price an
individual owned copy) and are shared across every instance owned of that set.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `as_of_date` | `Date` | Effective date of the market valuation |
| `market_value_eur` | `NUMERIC(10,2)` | Current market value, EUR (*custo atual*) |
| `value_type` | `Enum` | `NEW_SEALED` \| `USED_COMPLETE` \| `PARTS_OUT` |
| `source` | `Enum` | `MANUAL` \| `BRICKECONOMY` \| `BRICKLINK` — manual entry vs. an opt-in automated fetch from that specific provider |
| `note` | `String?` | Optional note explaining valuation context |
| `created_at` | `Timestamp` | Snapshot creation timestamp |

---

#### 4. `StorageLocation` (Physical Storage Hierarchy)
Hierarchical tree structure for tracking physical storage containers and rooms.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `entity_id` | `UUID` | Household / User isolation scope |
| `name` | `String` | Primary location name (e.g., `"Garagem"`, `"Escritório"`) |
| `container` | `String?` | Specific bin/box identifier (e.g., `"Caixa 3"`, `"Prateleira A"`) |
| `parent_location_id` | `UUID?` | Foreign key to parent `StorageLocation` for nested hierarchies |
| `description` | `String?` | Additional details about access or storage conditions |
| `capacity_pct` | `Integer?` | Hand-annotated estimate of how full this location is, **0–100** (e.g. `0`, `25`, `50`, `75`, `100`); set and updated manually by the user, never computed from `stored_count`. Needed because many locations are irregular/repurposed containers (e.g. an old TV box) with no meaningful "how many sets fit" number. `NULL` = not tracked. Typically set on leaf containers (boxes), not parent rooms. |
| `is_active` | `Boolean` | Active status flag (`default: true`) |

---

#### 5. `MissingPart` (Incomplete Set Detail)
Itemized tracking for individual missing pieces when `completeness_status = MISSING_PARTS`.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_instance_id` | `UUID` | Foreign key to `LegoSetInstance` |
| `part_ref` | `String?` | Part or Design ID (e.g., BrickLink part number `"3001"`) |
| `color` | `String?` | Official LEGO or BrickLink color name (e.g., `"Red"`, `"Dark Tan"`) |
| `description` | `String` | Brief text description of the missing piece |
| `quantity_missing` | `Integer` | Number of missing units (`default: 1`) |
| `quantity_total` | `Integer?` | Total required count of this piece in the set |
| `is_critical` | `Boolean` | Flag if part prevents building key structural/aesthetic parts |
| `estimated_replacement_cost_eur` | `NUMERIC(10,2)?` | Estimated unit replacement cost, EUR |
| `bricklink_part_url` | `String?` | Direct link to buy the specific part on BrickLink |
| `resolved` | `Boolean` | Status flag (`true` when piece has been acquired/replaced) |
| `notes` | `Text?` | Optional details regarding replacement efforts |

---

#### 6. `LegoImage` (Visual Media Attachments)
Stores web reference images and user-uploaded photographs. `SET`/`BOX` images
are generic catalog artwork shared by every owned copy of a set, so they attach
to the **model**; `CUSTOM` images are a specific copy's own photos (box wear,
actual build), so they attach to the **instance**. Exactly one of
`lego_set_model_id` / `lego_set_instance_id` is populated, matching `image_kind`.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID?` | Foreign key to `LegoSetModel`; populated when `image_kind IN (SET, BOX)` |
| `lego_set_instance_id` | `UUID?` | Foreign key to `LegoSetInstance`; populated when `image_kind = CUSTOM` |
| `image_kind` | `Enum` | `SET` \| `BOX` \| `CUSTOM` |
| `source` | `Enum` | `URL` (external web image) \| `UPLOAD` (user file) |
| `url` | `String?` | External URL string (stored when `source = URL`) |
| `document_id` | `UUID?` | Foreign key to Core `Document` storage (stored when `source = UPLOAD`) |
| `is_primary` | `Boolean` | Primary thumbnail flag, scoped to whichever parent is populated (*strictly one `true` per model, and independently one `true` per instance*) |
| `caption` | `String?` | Optional image label or description |
| `created_at` | `Timestamp` | Record creation timestamp |

---

#### 7. `ExternalListing` (Marketplace Reference Links)
Stores quick access links to external market valuation and catalog tools.
Listings apply to the **set model** (the same BrickLink/BrickEconomy page is
shared by every copy owned of that set).

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `provider` | `Enum` | `BRICKLINK` \| `BRICKECONOMY` \| `REBRICKABLE` \| `OTHER` — `REBRICKABLE` is a community parts/instructions catalog reference only, never a pricing source |
| `url` | `String` | Direct web link to the set listing |
| `last_checked_at` | `Timestamp?` | Last successful market check timestamp |
| `last_seen_value_eur` | `NUMERIC(10,2)?` | Market value fetched during the last check, EUR |

---

### Computed & Derived Fields (Real-Time Engine Logic)
These values are dynamically evaluated by application logic or database views:

- `owned_copies_count` (per `LegoSetModel`) = `COUNT(LegoSetInstance)` WHERE in-scope (see definition above)
- `current_value_eur` (per instance) = latest `LegoValuation.market_value_eur` for the instance's `lego_set_model_id`, matching the `value_type` derived **from `build_state` alone** (`SEALED` → `NEW_SEALED`; otherwise → `USED_COMPLETE`; user-overridable to `PARTS_OUT`), **then reduced by `estimated_missing_cost_eur`** (floored at 0) when `completeness_status = MISSING_PARTS` — this is how completeness factors into value, rather than changing the `value_type` band itself
- `appreciation_eur` = `current_value_eur - acquisition_cost_eur` — only computed for in-scope instances
- `roi_pct` = `(appreciation_eur / acquisition_cost_eur) * 100` — always **unrealized**; `NULL` for instances that are not in-scope
- `realized_gain_eur` (informational only, per instance) = `sale_price_eur - acquisition_cost_eur` — only when `ownership_status = SOLD`; never included in the collection's headline ROI/appreciation KPIs
- `is_retired` (per `LegoSetModel`) = `retired_year IS NOT NULL`
- `missing_parts_count` = `SUM(MissingPart.quantity_missing)` WHERE `resolved = FALSE`
- `estimated_missing_cost_eur` = `SUM(MissingPart.estimated_replacement_cost_eur * MissingPart.quantity_missing)` WHERE `resolved = FALSE`
- `stored_count` (per `StorageLocation`) = `COUNT(LegoSetInstance)` WHERE `storage_location_id` = this location AND in-scope (see definition above) — an informational count, independent of `capacity_pct`
- `remaining_capacity_pct` (per `StorageLocation`) = `100 - capacity_pct` (`NULL` if `capacity_pct IS NULL`)
- `is_full` (per `StorageLocation`) = `capacity_pct >= 100`

## Functional Requirements
- **FR-9.1 Catalog Model CRUD.** Create/edit/soft-delete `LegoSetModel` rows (set identity: number, name, theme, year, piece/minifig count). Find-or-create by `set_number` when adding an instance so repeat copies of the same set reuse the same model row.
- **FR-9.2 Set Metadata Pre-fill (opt-in).** On entering a `set_number`, optionally pre-fill name/theme/year/piece_count/minifig_count from a local seed table or an opt-in external lookup (BrickLink/BrickEconomy). Off by default (privacy); pre-filled fields are always user-editable and never overwrite manual edits.
- **FR-9.3 Instance CRUD.** Create/edit/soft-delete `LegoSetInstance` rows (one per physical copy) with acquisition, storage, build state, completeness, physical condition, and ownership fields. Minimal required input: a `LegoSetModel` reference (via `set_number` or custom name) + `acquisition_cost_eur`; everything else optional.
- **FR-9.4 Set Grouping & Copy Count.** For any `LegoSetModel`, expose `owned_copies_count` and the list of its `LegoSetInstance` rows, so the user can see how many copies of a set they own and drill into each copy's individual details.
- **FR-9.5 Acquisition Cost & Transaction Link.** Record `acquisition_cost_eur` (custo real, EUR) per instance and optionally set `acquisition_transaction_id` to the originating bank `Transaction` (M2) — a direct foreign key, consistent with how M3/M4/M5 link their own expense records to a transaction — so the purchase reconciles with the ledger.
- **FR-9.6 Current Market Value Tracking.** Record `LegoValuation` snapshots (custo atual, EUR) against a `LegoSetModel` manually, or via opt-in refresh from BrickEconomy/BrickLink. Snapshots are **immutable**; corrections append a new row. Track value by type (new-sealed vs used-complete vs parts-out); all instances of the same model share the same valuation history.
- **FR-9.7 Storage Location Management.** Assign each instance to a `StorageLocation` (hierarchical: room → container). CRUD locations; view "what's in this box" and "where is this set". Track an optional hand-annotated `capacity_pct` per location and surface remaining percentage / full status (see FR-9.13).
- **FR-9.8 Build State, Completeness & Physical Condition.** Track `build_state`, `completeness_status`, and `physical_condition` as three independent fields on each instance (e.g. a set can be `BUILT` + `MISSING_PARTS` + `GOOD` simultaneously). When `completeness_status = MISSING_PARTS`, itemize `MissingPart` rows (part ref, color, qty, criticality, est. replacement cost, BrickLink part link, resolved flag).
- **FR-9.9 Ownership Lifecycle.** Track `ownership_status` per instance (`IN_COLLECTION` \| `LISTED_FOR_SALE` \| `SOLD` \| `GIFTED_AWAY` \| `DONATED` \| `LOST_OR_DAMAGED` \| `DISPOSED`). When set to `SOLD`, capture `sale_price_eur` and `sale_date`. Instances that are not in-scope (see definition in Data Model) are excluded from collection value and net-worth contribution, but remain visible in history unless soft-deleted. Every `ownership_status` change is captured in `AuditLog` (before/after), which is the source of truth for reconstructing "how many copies did I own on date X" trends — no separate status-history table is needed.
- **FR-9.10 Reference Links.** Store one or more `ExternalListing` URLs (BrickLink, BrickEconomy) per `LegoSetModel`, shared by all its owned instances; one-click open. No scraping unless the user explicitly enables refresh.
- **FR-9.11 Images.** Attach representative images either to the **set model** (`SET`/`BOX` catalog artwork, shared by every owned copy — either a **web URL**, referenced not copied, or a **user-uploaded photo** stored as a Core `Document`, magic-byte validated, served via signed URL) or to a specific **instance** (`CUSTOM` photos of that exact copy). One primary thumbnail per model, and independently one primary `CUSTOM` thumbnail per instance; the instance's own photo takes display precedence over the model's image when present.
- **FR-9.12 Collection Analytics.** Compute per-instance and collection-wide **unrealized** ROI, appreciation, value by theme, retired-set premium, and completeness stats. Realized sale data (`sale_price_eur`, `sale_date`) is surfaced per instance but excluded from these aggregate KPIs.
- **FR-9.13 Storage Capacity.** For each `StorageLocation`, let the user manually set/update `capacity_pct` (0–100) as their own estimate of fullness; compute `remaining_capacity_pct` and `is_full` from it; support filtering/highlighting locations that are full or near-full (e.g. "which boxes are full?"). `stored_count` (instance count) is shown alongside as an independent, always-computed metric — the two are not required to agree (a box with 3 large sets can read 100% while a box with 20 small polybags reads 40%).
- **FR-9.14 Net-Worth Contribution.** Expose the collection's total `current_value_eur` (in-scope instances only) to Assets (M6) as a `COLLECTIBLE` asset class so it rolls into household net worth (entity-scoped). All values are EUR; no FX conversion is required.
- **FR-9.15 Catalog Discovery.** Support search, filtering, sorting, and pagination across relevant fields, including set number, name, theme, storage location, build state, completeness, physical condition, ownership status, retirement status, acquisition cost, current value, piece count, and minifigure count.
## UI / Screens

- **UX-9.1 Module Navigation.** The LEGO module must provide two primary areas:
  - `Overview`, focused on collection metrics and trends.
  - `Collection`, focused on catalog navigation and management.
- **UX-9.2 Collection Overview.** `Overview` is the default landing view of the module.
  - **KPIs:**
    - Total Cost — sum of `acquisition_cost_eur` across in-scope instances
    - Current Value — sum of the latest valid valuations across in-scope instances
    - Global ROI — unrealized: `(Current Value - Total Cost) / Total Cost × 100`
    - Number of Unique Sets — count of active `LegoSetModel` rows with ≥1 in-scope instance
    - Number of Copies Owned — count of in-scope instances (`owned_copies_count` summed)
    - Number of Retired Sets — count of active `LegoSetModel` rows with a retirement year and ≥1 in-scope instance
    - Total Piece Count — sum of `piece_count` across in-scope instances
  - **Analytics:**
    - Sets by theme
    - Sets by price bracket
    - Sets by piece-count range
    - Historical total cost and current market value
    - Historical number of copies owned
  - Monetary and quantity series must remain clearly distinguishable when presented
    in the same visualization.
- **UX-9.3 Collection Workspace.** `Collection` must provide a data-first,
  high-density catalog optimized for search, comparison, and management. Rows
  represent individual owned copies (instances); an optional "group by set"
  view rolls copies of the same `LegoSetModel` together and shows the copy count.
  - **Primary information:**
    - Thumbnail (the instance's own `CUSTOM` photo if present, else the model's primary `SET`/`BOX` image), set number, set name, and external reference
    - Acquisition cost, current value, and unrealized ROI
    - Theme, piece count, minifigure count, release year, and retirement status
    - Storage location, build state, completeness, physical condition, and ownership status
    - Short description and notes preview
  - **Discovery and interactions:**
    - Global search across set number, name, description, and notes
    - Combinable filters for relevant structured fields, including theme, location,
      build state, completeness, physical condition, ownership status, price range,
      piece-count range, minifigure count, release year, and retirement status
    - Sorting and pagination
    - Efficient access to view, edit, and soft-delete actions
    - Progressive disclosure for missing parts, extended notes, valuation history,
      transaction links, images, and other secondary information
- **UX-9.4 Add and Edit Set Workflow.**
  - An `Add LEGO Set` action must be accessible from both `Overview` and `Collection`.
  - The flow begins with `set_number`; custom or MOC builds may use free-form entry.
  - When requested, the system retrieves available metadata from configured sources,
    including name, theme, release year, piece count, minifigure count, and image.
  - If the `set_number` already exists as a `LegoSetModel`, the user is offered to
    add another copy (instance) of that same set rather than duplicating the model.
  - Retrieved values must remain editable and must not overwrite later manual changes.
  - Before creation, the user can review and complete acquisition cost, storage
    location, build state, completeness, physical condition, purchase source,
    notes, and images.
  - Editing uses the same validation rules and preserves existing manual values.
- **UX-9.5 Set Details.** Users must be able to consult and manage:
  - Identity and complete metadata
  - Acquisition cost, current value, unrealized ROI, and valuation history
  - Sale price and sale date, when `ownership_status = SOLD` (shown separately from ROI)
  - Storage location, build state, completeness, and physical condition
  - Missing parts
  - Notes and transaction links
  - External references
  - Image gallery and primary image (the model's `SET`/`BOX` catalog images plus this copy's own `CUSTOM` photos, if any)
- **UX-9.6 Storage Management.**
  - Present storage locations hierarchically, such as room → container or box.
  - Support creation, editing, soft deletion, and consultation of location contents.
  - Allow users to identify both where a set is stored and which sets are stored
    in a selected location.
  - Show, per location, the current `stored_count` (instance count) alongside the
    user's hand-annotated `capacity_pct` (0/25/50/75/100 or free entry), its
    `remaining_capacity_pct`, and an `is_full` indicator; support filtering/sorting
    locations by fullness (e.g. "which boxes are full?"). Editing `capacity_pct`
    is a manual quick-action (e.g. a slider or preset buttons), never auto-calculated.
- **UX-9.7 Missing Parts Management.**
  - For incomplete sets, allow users to maintain missing-part records containing:
    - Part reference
    - Color
    - Missing quantity
    - Criticality
    - Estimated replacement cost
    - Resolution status
    - External part reference

## Proposed API Surface
The following API surface is indicative. It may be refined during implementation, provided that all required capabilities and business rules remain supported.

### Collection Overview
- `GET /collectibles/overview`
  - Returns aggregate KPIs, collection distributions, and historical value trends.

### Set Models (Catalog Identity)
- `GET /collectibles/models`
  - Returns set models with filtering, searching, and each model's `owned_copies_count`.
- `POST /collectibles/models`
  - Creates a set model (rarely called directly; normally created implicitly by `POST /collectibles`).
- `POST /collectibles/models/lookup`
  - Retrieves available set metadata from configured external sources using a set number.
  - Does not create or modify a model.
- `GET /collectibles/models/{modelId}`
  - Returns model details, external listings, and valuation summary.
- `PATCH /collectibles/models/{modelId}`
  - Updates the model.
- `DELETE /collectibles/models/{modelId}`
  - Soft-deletes the model. Blocked while any non-deleted (`is_active = true`) `LegoSetInstance` row references it, regardless of ownership status — even `SOLD` copies need the model's valuation/reference-link history intact.
- `GET /collectibles/models/{modelId}/instances`
  - Returns every owned copy of this set.

### Collectibles (Owned Instances)
- `GET /collectibles`
  - Returns the owned-copy catalog with filtering, sorting, searching, and pagination.
- `POST /collectibles`
  - Creates an owned copy (instance). Accepts a `set_number` (find-or-create on the model) or an explicit `lego_set_model_id`.
- `GET /collectibles/{collectibleId}`
  - Returns the instance details.
- `PATCH /collectibles/{collectibleId}`
  - Updates the instance.
- `DELETE /collectibles/{collectibleId}`
  - Soft-deletes the instance.

### Valuations
- `GET /collectibles/models/{modelId}/valuations`
  - Returns the valuation history for the set (shared by all owned copies).
- `POST /collectibles/models/{modelId}/valuations`
  - Adds a valuation snapshot.

### Storage Locations
- `GET /storage-locations`
  - Returns locations including `stored_count`, `capacity_pct`, `remaining_capacity_pct`, and `is_full`.
- `POST /storage-locations`
- `GET /storage-locations/{locationId}`
  - Returns location details and its stored instances.
- `PATCH /storage-locations/{locationId}`
- `DELETE /storage-locations/{locationId}`

### Net-Worth Integration
- `GET /collectibles/net-worth-contribution`
  - Returns the collection's aggregate current value (EUR) for inclusion in the net-worth calculation.

## Analytics & KPIs
- Collection totals: Σ custo real, Σ custo atual, unrealized gain, overall unrealized ROI % (EUR).
- Per-instance appreciation and unrealized ROI; top gainers / losers.
- Value by theme / subtheme (donut) and by acquisition year.
- Retired vs active premium (avg ROI of retired sets).
- Completeness: % complete, count with missing parts, Σ estimated replacement cost.
- Storage utilization: copies and value per location; count of full / near-full locations.
- Ownership pipeline: count and current market value of instances by `ownership_status` (e.g. `LISTED_FOR_SALE`).
- Realized sales (informational, reported separately from ROI/appreciation): count of `SOLD` instances, Σ `sale_price_eur`, Σ `realized_gain_eur`.

## Edge Cases & Validation
- **Valuation immutability:** corrections append a new `LegoValuation` (against the `LegoSetModel`); prior rows read-only (consistent with M6 snapshots).
- **Missing/invalid set number:** allow free-form custom items (`set_number` optional, `is_custom = true` for non-catalog builds/MOCs); pre-fill simply unavailable.
- **Multi-copy ownership:** each physical copy is its own `LegoSetInstance` row (own condition/storage/cost/ownership status); all copies of the same set share one `LegoSetModel` row. `owned_copies_count` aggregates in-scope instances per model (see definition in Data Model) — there is no `quantity` field on the instance.
- **Currency:** all monetary fields (`acquisition_cost_eur`, `market_value_eur`, `sale_price_eur`, `estimated_replacement_cost_eur`) are **EUR-only**; no `currency` field or FX conversion is modeled in this module. Net-worth rolls up directly in EUR (consistent with M6).
- **Ownership lifecycle transitions:** setting `ownership_status = SOLD` requires `sale_price_eur` and `sale_date`; changing away from `SOLD` clears both (an instance cannot be simultaneously "sold" and actively owned). Non-active statuses (`SOLD`, `GIFTED_AWAY`, `DONATED`, `LOST_OR_DAMAGED`, `DISPOSED`) are excluded from current-value/ROI aggregates and net-worth contribution but remain visible in history.
- **Deleting a `LegoSetModel`** with any non-deleted (`is_active = true`) instance, regardless of ownership status → block (reassign or remove instances first); even `SOLD`/`DISPOSED` instances still need the model's valuation/reference-link history.
- **Sealed yet missing parts:** `build_state = SEALED` combined with `completeness_status = MISSING_PARTS` is unusual but legitimate (e.g. a known factory packaging shortage reported by the community for that batch, without opening the box) — not a data-entry error; `current_value_eur` still nets out `estimated_missing_cost_eur` in this case.
- **Ownership-status history:** there is no dedicated append-only status-history table; the "Historical number of copies owned" trend (UX-9.2) and any "who owned what on date X" reconstruction rely on `AuditLog` before/after entries for `LegoSetInstance.ownership_status`/`is_active` changes. If `AuditLog` ever stops capturing full field-level diffs, this trend must be deferred until a dedicated history table is added.
- **Image source integrity:** URL images are **referenced** (store URL only, never hotlink-copy copyrighted images); uploads validated by magic bytes and stored as Core `Document`.
- **Stale external value:** if last refresh > user-set staleness (e.g. 90 days), show a "value may be outdated" badge; never silently degrade.
- **Deleting a storage location** with contents → block or reassign (no orphaned instances).
- **Assigning an instance to a full location:** `is_full` locations (hand-annotated `capacity_pct = 100`) show a warning but do not hard-block assignment (physical reality can flex); `capacity_pct` is not recalculated from `stored_count`, so the user may need to update it manually after adding or removing items.
- **Capacity is subjective by design:** `capacity_pct` is a hand-annotated estimate, not derived from `stored_count` — the two can diverge (e.g. a box with 3 large sets may read 100% while the same box with 20 small polybags reads 40%). This is intentional to support irregular/repurposed containers (e.g. an old TV or appliance box) where a fixed "slot count" isn't meaningful.

## Additional / Enriched Requirements
- **Sealed vs built vs parts-out valuation** — three value types tracked separately per set model; the applicable one drives net worth based on each instance's `build_state`.
- **Insurance/replacement report** — export collection with custo atual for home-insurance documentation.
- **Sale readiness** — mark `ownership_status = LISTED_FOR_SALE`, compare custo atual across providers, estimate potential net proceeds. Recording an actual sale (`SOLD` + `sale_price_eur` + `sale_date`) is kept for historical record only and never alters the collection's unrealized ROI/appreciation KPIs.
- **Barcode/box QR scan (future)** — scan the box barcode to resolve `set_number` for fast entry.
- **Instructions & minifig inventory (future)** — optional per-instance minifig checklist reusing the `MissingPart` pattern.
- **Storage capacity alerts (future)** — notify when a location nears or reaches `capacity_pct = 100`.

## Open Questions / Decisions
1. **External metadata/value source?** → *BrickEconomy for market value, BrickLink for parts/price; both opt-in, off by default; manual entry always works standalone.*
2. **Model vs. instance split?** → *One `LegoSetInstance` row per physical copy, referencing a shared `LegoSetModel` row per unique set; supports both copy-count aggregation and per-copy tracking without denormalizing set metadata onto every copy.*
3. **Store images or reference URLs?** → *Both supported; URLs referenced (no copyright copy), user photos uploaded as `Document`. `SET`/`BOX` catalog images attach to the `LegoSetModel` (shared by every copy); `CUSTOM` photos attach to the specific `LegoSetInstance`.*
4. **Its own asset class or part of M6?** → *Own module for the rich catalog; exposes an aggregate `COLLECTIBLE` asset to M6 net worth (avoids duplicating asset UI).*
5. **Value type driving net worth?** → *`value_type` is derived from `build_state` alone (`SEALED`→new, otherwise→used-complete; user-overridable to `PARTS_OUT`). `completeness_status = MISSING_PARTS` does not change the `value_type`; instead it reduces `current_value_eur` by `estimated_missing_cost_eur`.*
6. **Refresh cadence?** → *User-set (default monthly) when enabled; manual "refresh now" always available.*
7. **Is `LegoSetModel` shared globally or per household?** → *Entity-scoped, like every other entity in this app; a globally shared catalog cache (deduplicated across households) is a possible future optimization, deferred to avoid cross-tenant data-isolation questions.*
8. **Storage capacity unit?** → *`capacity_pct` is a hand-annotated percentage (0–100) that the user sets/updates manually per location — deliberately **not** computed from `stored_count`. Many storage locations are irregular/repurposed containers (e.g. an old TV box) where a fixed "how many sets fit" number isn't meaningful, but the user can still eyeball "this box is about 75% full."*
9. **Ownership lifecycle values?** → *`IN_COLLECTION`, `LISTED_FOR_SALE`, `SOLD`, `GIFTED_AWAY`, `DONATED`, `LOST_OR_DAMAGED`, `DISPOSED` — chosen to cover realistic disposition paths while keeping `SOLD` distinct so realized-sale data can be captured without affecting unrealized ROI.*
10. **Is `AuditLog` sufficient for ownership-status history, or is a dedicated table needed?** → *Sufficient: the core `AuditLog` contract (`before`/`after` JSONB per mutation) already captures every `ownership_status` change with a timestamp; a dedicated status-history table is deferred unless `AuditLog` stops guaranteeing field-level diffs.*
11. **`CRAWLER` as a `LegoValuation.source`?** → *Struck — redundant with the opt-in `BRICKLINK`/`BRICKECONOMY` automated-fetch sources; `MANUAL` covers everything else.*

## Definition of Done
- [ ] `LegoSetModel` CRUD; find-or-create by `set_number`; soft-delete blocked while any non-deleted instance references it (regardless of ownership status).
- [ ] `LegoSetInstance` CRUD (minimal required: model reference + `acquisition_cost_eur`); soft-delete; no `quantity` field — one row per physical copy.
- [ ] `owned_copies_count` aggregation renders correctly per model (in-scope instances only).
- [ ] Optional metadata pre-fill (opt-in) never overwrites manual edits.
- [ ] Valuation snapshots (per model) immutable; latest-value resolver + unrealized appreciation/ROI computed and tested, including the `estimated_missing_cost_eur` deduction when `completeness_status = MISSING_PARTS`; `sale_price_eur`/`sale_date` excluded from ROI math.
- [ ] Ownership lifecycle enforced (`SOLD` requires `sale_price_eur` + `sale_date`; non-in-scope statuses excluded from net worth); `AuditLog` entries verified sufficient to reconstruct ownership-status history.
- [ ] Storage locations (hierarchical) CRUD; `capacity_pct` is user-editable (0–100, hand-annotated, never auto-computed); `remaining_capacity_pct`/`is_full` derived from it and tested; `stored_count` computed independently; "contents of container" view.
- [ ] `build_state` + `completeness_status` + `physical_condition` tracked as independent fields, with itemized `MissingPart` and estimated replacement cost.
- [ ] External links (BrickLink/BrickEconomy) stored per model and one-click openable; refresh opt-in, off by default, non-blocking.
- [ ] Images: URL reference **and** user upload (magic-byte validated `Document`, signed URL); `SET`/`BOX` images scoped to the model, `CUSTOM` scoped to the instance; one primary thumbnail per model and independently per instance enforced.
- [ ] Purchase linkable to a bank `Transaction` (M2) via direct FK.
- [ ] Collection analytics (totals, unrealized ROI, value-by-theme, completeness) render; realized sale figures shown separately.
- [ ] Net-worth contribution exposed to M6 as `COLLECTIBLE` asset class; entity-scoped; EUR-only (no FX conversion).
- [ ] Seed: a few example sets (e.g. 10307 Eiffel Tower, 75192 Millennium Falcon) with cost, value, location, and one image each.
- [ ] Tests: unrealized ROI/appreciation math (incl. missing-parts deduction), immutable valuation, missing-cost rollup, storage capacity math, image source validation; ≥80% coverage on domain logic.

## Integration Contract
- **Exposes:** aggregate `current_value_eur` (entity-scoped, EUR) to Assets (M6) as a `COLLECTIBLE` asset class → household net worth; `LegoSetInstance.acquisition_transaction_id` as a direct FK reconciled against Banking (M2) transactions; collection value/ROI series to Dashboards (M8).
- **Consumes:** `Entity` (ownership/attribution + RBAC), `Merchant` (acquisition source), `Transaction` (M2, purchase link), `Document` (uploaded images), `Tag`, `Setting` (opt-in external refresh toggle + cadence), `AuditLog` (mutations; also the source for reconstructing ownership-status history trends), `ProcessingJob` (refresh jobs).
- **Guarantees:** external providers are never contacted unless explicitly enabled; valuations immutable; images either referenced (URL) or validated uploads; all monetary values are EUR-only.

TODO 
External Systems
Rebrickable
BrickLink
BrickEconomy
Net Worth / Asset Management module