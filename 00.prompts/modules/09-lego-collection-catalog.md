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

### US01. Catalog Set Registration
As a user, I want to add a LEGO set to the catalog by entering its set number so that the system can retrieve metadata (name, theme, piece count, release year, recommended age, default image) from configured catalog providers (e.g., Rebrickable, Brickset, BrickLink), reducing manual entry.

### US02. Instance Lifecycle & Condition Tracking
As a user, I want to track individual physical copies (instances) of a set—including acquisition cost, purchase date, physical condition (Sealed/Used), completeness, build state, and storage location—so I know the exact status and location of every item I own.

### US03. Inventory Search & Multi-Facet Filtering
As a user, I want to quickly search and filter my collection by set number, set name, theme, physical location, build state, condition, or any inventory lifecycle status.

### US04. Market Valuation & Performance Tracking
As a user, I want the system to track the current market value of my active collection so I can evaluate unrealized gains, unrealized ROI %, and value evolution over time based on current market estimates versus historical acquisition cost.

### US05. Collection Analytics & Distribution
As a user, I want visual analytics summarizing total asset value, total piece count, top themes, physical storage distribution, condition breakdowns, and completeness metrics across my active collection.

### US06. Market Integration & Refresh
As a user, I want to trigger manual or scheduled market value refreshes from external valuation providers and quickly navigate to external marketplace listings (e.g., BrickLink) for any set in my catalog.

### US07. Visual Catalog & Image Management
As a user, I want to assign custom image references or select primary cover images for both the catalog set and individual instances so I can visually browse my collection.

### US08. Net-Worth Integration
As a user, I want the aggregate current market value of all active, in-scope instances (`IN_COLLECTION`, `LISTED_FOR_SALE`) automatically fed into the household net-worth module as a single asset class stream.

### US09. Duplicate & Set Instance Grouping
As a user, I want the UI to aggregate multiple instances under their parent catalog set while allowing me to inspect, edit, or manage each physical copy's independent history and attributes.

### US10. Lifecycle Transitions & Deletion Controls
As a user, I want to move an instance between `IN_COLLECTION` and `LISTED_FOR_SALE`, record its final disposition (`SOLD`, `GIFTED_AWAY`, `DONATED`, `LOST_OR_DAMAGED`, or `DISPOSED`), and soft-delete erroneous entries without losing legitimate ownership history.

## Data Model

### Entities & Attributes

All monetary attributes are denominated in **EUR only** (no multi-currency, no FX conversion). Values are stored as `NUMERIC(10,2)` decimal EUR amounts (e.g., `19.99`); UI displays them pt-PT-formatted (e.g., `19,99€`).

The catalog identity of a set (`LegoSetModel`) is separated from each physical copy owned (`LegoSetInstance`). This lets a user see how many copies of a given set they own, while each copy still carries its own cost, storage, build state, completeness, physical condition, and ownership lifecycle.

**Definition — in-scope instance.** Unless stated otherwise, every KPI, aggregate, and net-worth contribution in this module operates over *in-scope* `LegoSetInstance` rows: `is_deleted = false` AND `ownership_status IN (IN_COLLECTION, LISTED_FOR_SALE)`. This is distinct from `is_deleted` alone, which is only a soft-delete flag — a `SOLD` instance can remain `is_deleted = false` (kept for history) while being out of scope for value/ROI KPIs and net worth.

#### 1. `LegoSetModel` (Catalog / Reference Entity)
Represents the *identity* of a LEGO set (or a custom/MOC build) — the metadata shared by every physical copy owned of that set. One row exists per unique `set_number` (or per custom build) within an entity's scope; multiple owned copies reference the same `LegoSetModel` row via `LegoSetInstance`.

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
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `created_at` | `Timestamp` | Record creation timestamp |
| `updated_at` | `Timestamp` | Record last updated timestamp |
| `deleted_at` | `Timestamp?` | Soft-delete timestamp (`NULL` until deleted) |

Unique constraint: `(entity_id, set_number)` when `set_number IS NOT NULL`.

---

#### 2. `LegoSetInstance` (Owned Physical Copy)
Represents exactly **one** physical copy owned by the household. Each copy is always its own row — there is no `quantity` field; owning three copies of the same set means three `LegoSetInstance` rows referencing the same `LegoSetModel`.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `entity_id` | `UUID` | Household / User isolation scope |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `acquisition_date` | `Date?` | Date the copy was acquired |
| `acquisition_cost_eur` | `NUMERIC(10,2)` | Actual purchase price paid, EUR (*custo real*); `0.00` for gifts or non-monetary acquisitions |
| `acquisition_source` | `Enum?` | `RETAIL` \| `SECONDHAND` \| `GIFT` \| `OTHER` |
| `acquisition_merchant_id` | `UUID?` | Optional reference to merchant entity |
| `acquisition_transaction_id`| `UUID?` | Optional link to banking ledger transaction (Module 2) |
| `storage_location_id` | `UUID?` | Foreign key to `StorageLocation` |
| `build_state` | `Enum?` | `SEALED` \| `BUILT` \| `PARTIALLY_BUILT` \| `DISASSEMBLED` — whether the copy is currently assembled |
| `completeness_status` | `Enum` | `COMPLETE` \| `MISSING_PARTS` \| `UNKNOWN` — independent of build state and completeness (`default: UNKNOWN`) |
| `physical_condition` | `Enum?` | `NEW` \| `GOOD` \| `WORN` \| `DAMAGED` — physical wear of box/pieces, independent of build state and completeness |
| `has_box` | `Boolean` | Indicates if original box is present (`default: true`) |
| `box_condition` | `Enum?` | `SEALED_MINT` \| `SHELF_WEAR` \| `OPEN_DAMAGED` \| `NO_BOX` — detailed packaging condition |
| `has_instructions` | `Boolean` | Indicates if instruction booklet is present (`default: true`) |
| `ownership_status` | `Enum` | `IN_COLLECTION` \| `LISTED_FOR_SALE` \| `SOLD` \| `GIFTED_AWAY` \| `DONATED` \| `LOST_OR_DAMAGED` \| `DISPOSED` — ownership lifecycle (`default: IN_COLLECTION`) |
| `valuation_type_override` | `Enum?` | `PARTS_OUT` only; when set, overrides the automatic valuation-band resolver |
| `sale_price_eur` | `NUMERIC(10,2)?` | Actual sale price received, EUR; set only when `ownership_status = SOLD` |
| `sale_date` | `Date?` | Date the copy was sold; set only when `ownership_status = SOLD` |
| `short_description` | `String?` | Concise 1-sentence summary specific to this copy (optional override) |
| `notes` | `Text?` | Free-text notes (e.g., box wear, missing piece list) |
| `is_deleted` | `Boolean` | Soft-delete flag, independent of `ownership_status` (`default: false`) |
| `created_at` | `Timestamp` | Record creation timestamp |
| `updated_at` | `Timestamp` | Record last updated timestamp |
| `deleted_at` | `Timestamp?` | Soft-delete timestamp (`NULL` until deleted) |

**Constraints & Rules:**
- `sale_price_eur` and `sale_date` must be non-null when `ownership_status = SOLD`.
- `sale_price_eur` and `sale_date` must be null when `ownership_status != SOLD`.
- `has_box = false` requires `box_condition = NO_BOX`; `box_condition = NO_BOX` requires `has_box = false`.

---

#### 3. `LegoValuation` (Market Price History)
Immutable, append-only records tracking current market value (*custo atual*) over time. Valuations apply to the **set model** (the market doesn't price an individual owned copy) and are shared across every instance owned of that set.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `as_of_date` | `Date` | Effective date of the market valuation |
| `market_value_eur` | `NUMERIC(10,2)` | Current market value, EUR (*custo atual*) |
| `value_type` | `Enum` | `NEW_SEALED` \| `USED_COMPLETE` \| `PARTS_OUT` |
| `source` | `Enum` | `MANUAL` \| `BRICKECONOMY` \| `BRICKLINK` \| `BRICKSET` |
| `note` | `String?` | Optional note explaining valuation context |
| `created_at` | `Timestamp` | Snapshot creation timestamp |

**Valuation Engine Lookup Rule:**
To estimate an instance's current market value:
- If `valuation_type_override = PARTS_OUT` $\rightarrow$ Map to `PARTS_OUT` valuation.
- Otherwise, if `build_state = SEALED` AND `physical_condition = NEW` $\rightarrow$ Map to `NEW_SEALED` valuation.
- Otherwise (including unknown build state or physical condition) $\rightarrow$ Map to `USED_COMPLETE` valuation.

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
| `capacity_pct` | `Integer?` | Hand-annotated estimate of how full this location is, **0–100**. `NULL` = not tracked. |
| `is_deleted` | `Boolean` | Soft-delete flag (`default: false`) |
| `deleted_at` | `Timestamp?` | Soft-delete timestamp (`NULL` until deleted) |

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
Stores web reference images and user-uploaded photographs. `SET`/`BOX` images attach to the **model**; `CUSTOM` images attach to the **instance**.


| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID?` | Foreign key to `LegoSetModel`; populated when `image_kind IN (SET, BOX)` |
| `lego_set_instance_id` | `UUID?` | Foreign key to `LegoSetInstance`; populated when `image_kind = CUSTOM` |
| `image_kind` | `Enum` | `SET` \| `BOX` \| `CUSTOM` |
| `source` | `Enum` | `URL` (external web image) \| `UPLOAD` (user file) |
| `url` | `String?` | External URL string (stored when `source = URL`) |
| `document_id` | `UUID?` | Foreign key to Core `Document` storage (stored when `source = UPLOAD`) |
| `is_primary` | `Boolean` | Primary thumbnail flag, scoped to whichever entity is populated |
| `caption` | `String?` | Optional image label or description |
| `created_at` | `Timestamp` | Record creation timestamp |

**Constraints:**
- Integrity check: `(lego_set_model_id IS NOT NULL AND lego_set_instance_id IS NULL AND image_kind IN ('SET', 'BOX')) OR (lego_set_model_id IS NULL AND lego_set_instance_id IS NOT NULL AND image_kind = 'CUSTOM')`
- Source check: `source = URL` requires `url IS NOT NULL AND document_id IS NULL`; `source = UPLOAD` requires `document_id IS NOT NULL AND url IS NULL`.
- Partial unique indexes enforce at most one `is_primary = true` image per `lego_set_model_id` and independently per `lego_set_instance_id`.

---

#### 7. `ExternalListing` (Marketplace Reference Links)
Stores quick access links to external market valuation and catalog tools.
Listings apply to the **set model** (the same BrickLink/BrickEconomy page is
shared by every copy owned of that set).

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `lego_set_model_id` | `UUID` | Foreign key to `LegoSetModel` |
| `provider` | `Enum` | `BRICKLINK` \| `BRICKECONOMY` \| `REBRICKABLE` \| `BRICKSET` \| `OTHER` |
| `url` | `String` | Direct web link to the set listing |
| `last_checked_at` | `Timestamp?` | Last successful market check timestamp |
| `last_seen_value_eur` | `NUMERIC(10,2)?` | Market value fetched during the last check, EUR |

---

### Computed & Derived Fields (Real-Time Engine Logic)
These values are dynamically evaluated by application logic or database views:

- `owned_copies_count` (per `LegoSetModel`) = `COUNT(LegoSetInstance)` WHERE in-scope (see definition above)
- `current_value_eur` (per instance) = latest `LegoValuation.market_value_eur` for the instance's `lego_set_model_id`, matching the valuation-engine lookup rule above, **then reduced by `estimated_missing_cost_eur`** (floored at 0) when `completeness_status = MISSING_PARTS` — this is how completeness factors into value, rather than changing the automatic valuation band itself
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
- **FR-9.1 Catalog Model CRUD.** Create/edit/soft-delete/hard-delete `LegoSetModel` and `LegoSetInstances` rows (set identity: number, name, theme, year, piece/minifig count). Find-or-create by `set_number` when adding an instance so repeat copies of the same set reuse the same model row.
- **FR-9.2 Set Metadata Pre-fill.** On entering a `set_number`, pre-fill name/theme/year/piece_count/minifig_count from a local seed table or an configured catalog lookup (Rebrickable, Brickset, or BrickLink). pre-filled fields are always user-editable and never overwrite manual edits.
- **FR-9.3 Instance CRUD.** Create/edit/soft-delete `LegoSetInstance` rows (one per physical copy) with acquisition, storage, build state, completeness, physical condition, and ownership fields. Minimal required input: a `LegoSetModel` reference (via `set_number` or custom name) + non-null `acquisition_cost_eur` (use `0.00` for gifts); every other capture field is optional or has a documented default.
- **FR-9.4 Set Grouping & Copy Count.** For any `LegoSetModel`, expose `owned_copies_count` and the list of its `LegoSetInstance` rows, so the user can see how many copies of a set they own and drill into each copy's individual details.
- **FR-9.5 Acquisition Cost & Transaction Link.** Record `acquisition_cost_eur` (custo real, EUR) per instance and optionally set `acquisition_transaction_id` to the originating bank `Transaction` (M2) — a direct foreign key, consistent with how M3/M4/M5 link their own expense records to a transaction — so the purchase reconciles with the ledger.
- **FR-9.6 Current Market Value Tracking.** Record `LegoValuation` snapshots (custo atual, EUR) against a `LegoSetModel` manually, or via opt-in refresh from BrickEconomy/BrickLink. Snapshots are **immutable**; corrections append a new row. Track value by type (new-sealed vs used-complete vs parts-out); all instances of the same model share the same valuation history.
- **FR-9.7 Storage Location Management.** Assign each instance to a `StorageLocation` (hierarchical: room → container). CRUD locations; view "what's in this box" and "where is this set". Track an optional hand-annotated `capacity_pct` per location and surface remaining percentage / full status (see FR-9.13).
- **FR-9.8 Build State, Completeness & Physical Condition.** Track `build_state`, `completeness_status`, and `physical_condition` as three independent fields on each instance (e.g. a set can be `BUILT` + `MISSING_PARTS` + `GOOD` simultaneously). When `completeness_status = MISSING_PARTS`, itemize `MissingPart` rows (part ref, color, qty, criticality, est. replacement cost, BrickLink part link, resolved flag).
- **FR-9.9 Ownership Lifecycle.** Track `ownership_status` per instance (`IN_COLLECTION` \| `LISTED_FOR_SALE` \| `SOLD`). Allow movement between `IN_COLLECTION` and `LISTED_FOR_SALE`; either active state may move to a terminal disposition. When set to `SOLD`, capture `sale_price_eur` and `sale_date`; Reopening a terminal disposition is a corrected historical mutation and must be explicitly audited; reopening `SOLD` clears its sale fields. Instances that are not in-scope (see definition in Data Model) are excluded from collection value and net-worth contribution, but remain visible in history unless soft-deleted. Every create, soft-delete, and `ownership_status` change is captured in timestamped `AuditLog` before/after data, which is the source of truth for reconstructing "how many copies did I own on date X" trends — no separate status-history table is needed.
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
  - Monetary and quantity series must remain clearly distinguishable when presented in the same visualization.
- **UX-9.3 Collection Workspace.** `Collection` must provide a data-first,
  high-density catalog optimized for search, comparison, and management. Rows represent individual owned copies (instances); an optional "group by set" view rolls copies of the same `LegoSetModel` together and shows the copy count.
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
  - When requested, the system retrieves available metadata from configured sources, including name, theme, release year, piece count, minifigure count, and image.
  - If the `set_number` already exists as a `LegoSetModel`, the user is offered to add another copy (instance) of that same set rather than duplicating the model.
  - Retrieved values must remain editable and must not overwrite later manual changes.
  - Before creation, the user can review and complete acquisition cost, storage location, build state, completeness, physical condition, purchase source, notes, and images.
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
  - Allow users to identify both where a set is stored and which sets are stored in a selected location.
  - Show, per location, the current `stored_count` (instance count) alongside the user's hand-annotated `capacity_pct` (0/25/50/75/100 or free entry), its `remaining_capacity_pct`, and an `is_full` indicator; support filtering/sorting locations by fullness (e.g. "which boxes are full?"). Editing `capacity_pct` is a manual quick-action (e.g. a slider or preset buttons), never auto-calculated.
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

## 1. Collection Overview & Net-Worth
- `GET /collectibles/overview`
  - Returns aggregate headline KPIs (total unrealized value, total appreciation, portfolio ROI), condition distributions, theme breakdowns, and historical value trend snapshots.
- `GET /collectibles/net-worth-contribution`
  - Returns the collection's total aggregate current market value (EUR) operating strictly over in-scope instances (`is_deleted = false` AND `ownership_status IN ('IN_COLLECTION', 'LISTED_FOR_SALE')`).

## 2. Catalog Models (`LegoSetModel`)
- `GET /collectibles/models`
  - Returns set models with filtering (theme, retired status), search, and derived `owned_copies_count`.
- `POST /collectibles/models`
  - Creates a catalog set model manually or as a custom MOC build.
- `POST /collectibles/models/lookup`
  - Retrieves set metadata from configured external sources using a set number without mutating database state.
- `GET /collectibles/models/{modelId}`
  - Returns model details, external marketplace listings, primary cover image, and valuation history summary.
- `PATCH /collectibles/models/{modelId}`
  - Updates set model metadata (e.g., manual overrides).
- `DELETE /collectibles/models/{modelId}`
  - Soft-deletes the set model. Blocked while any active or historical instance (`is_deleted = false`) references it—even `SOLD` copies require model metadata for historical integrity.

## 3. Owned Physical Inventory (`LegoSetInstance`)
- `GET /collectibles/instances`
  - Returns a flat, paginated list of all physical copies across the collection with multi-facet filtering (status, location, build state, completeness, condition).
- `POST /collectibles/instances`
  - Registers a new physical copy under a given `lego_set_model_id` (implicitly creates the parent `LegoSetModel` via lookup if it does not yet exist).
- `GET /collectibles/models/{modelId}/instances`
  - Returns all physical copies referencing a specific catalog set model.
- `GET /collectibles/instances/{instanceId}`
  - Returns full details of an individual physical copy, including itemized missing parts, custom photos, transaction links, and exact storage location.
- `PATCH /collectibles/instances/{instanceId}`
  - Updates instance properties, physical condition, build state, storage location, or ownership lifecycle transitions. Active instances may move between `IN_COLLECTION` and `LISTED_FOR_SALE` or to a terminal disposition; `SOLD` requires `sale_price_eur` and `sale_date`.
- `DELETE /collectibles/instances/{instanceId}`
  - Soft-deletes (`is_deleted = true`) or hard-deletes an individual physical copy.

## 4. Itemized Deficits (`MissingPart`)
- `GET /collectibles/instances/{instanceId}/missing-parts`
  - Returns itemized missing pieces for a copy where `completeness_status = MISSING_PARTS`.
- `POST /collectibles/instances/{instanceId}/missing-parts`
  - Adds a missing part entry with replacement costs and BrickLink references.
- `PATCH /collectibles/instances/{instanceId}/missing-parts/{partId}`
  - Updates part details or flags it as `resolved = true` (which dynamically re-evaluates the instance's `estimated_missing_cost_eur`).
- `DELETE /collectibles/instances/{instanceId}/missing-parts/{partId}`
  - Removes a missing part entry.

## 5. Valuations & External Listings
- `GET /collectibles/models/{modelId}/valuations`
  - Returns historical market price snapshots for the catalog set model.
- `POST /collectibles/models/{modelId}/valuations`
  - Records a new market valuation snapshot (manual entry or external sync response).
- `GET /collectibles/models/{modelId}/listings`
  - Returns marketplace links (BrickLink, BrickEconomy, Rebrickable) and last-checked price points.

## 6. Media Attachments (`LegoImage`)
- `POST /collectibles/models/{modelId}/images`
  - Attaches set/box artwork to a catalog set model.
- `POST /collectibles/instances/{instanceId}/images`
  - Attaches custom photographs (actual box wear, built displays) to a specific physical copy.
- `PATCH /collectibles/images/{imageId}/primary`
  - Sets an image as the primary cover photo for its parent entity.
- `DELETE /collectibles/images/{imageId}`
  - Removes an image association.

## 7. Storage Hierarchy Locations
- `GET /collectibles/storage-locations`
  - Returns hierarchical storage locations including computed counts (`stored_count`), manually annotated `capacity_pct`, `remaining_capacity_pct`, and `is_full`.
- `POST /collectibles/storage-locations`
  - Creates a storage room or container.
- `GET /collectibles/storage-locations/{locationId}`
  - Returns location metadata and all active instances stored inside.
- `PATCH /collectibles/storage-locations/{locationId}`
  - Updates location details or parent-child hierarchy assignments.
- `DELETE /collectibles/storage-locations/{locationId}`
  - Soft-deletes a storage location. Blocked if active instances are assigned to it without reassignment.

## Analytics & KPIs
- Collection totals: Σ custo real, Σ custo atual, unrealized gain, overall unrealized ROI % (EUR).
- Per-instance appreciation and unrealized ROI; top gainers / losers.
- Value by theme / subtheme (donut) and by acquisition year.
- Retired vs active premium (avg ROI of retired sets).
- Completeness: % complete, count with missing parts, Σ estimated replacement cost.
- Storage utilization: copies and value per location; count of full / near-full locations.
- Ownership pipeline: count and current market value of instances by `ownership_status` (e.g. `LISTED_FOR_SALE`).
- Realized sales (informational, reported separately from ROI/appreciation): count of `SOLD` instances, Σ `sale_price_eur`, Σ `realized_gain_eur`.

## Edge Cases & Validation Bsusiness rules

## 1. Valuation & Financial Rules
- **Valuation Immutability:** Corrections to market value append a new `LegoValuation` snapshot against the parent `LegoSetModel`. Prior rows remain strictly read-only for audit integrity.
- **Single-Currency Enforcement:** All monetary attributes (`acquisition_cost_eur`, `market_value_eur`, `sale_price_eur`, `estimated_replacement_cost_eur`) are EUR-only. No `currency` field or FX conversion logic exists in this module; aggregate net-worth calculations roll up directly in EUR.
- **Zero-Cost Acquisitions (Gifts / Non-Monetary Acquisitions):** Record `acquisition_cost_eur = 0.00` for gifts or promo items. `roi_pct` evaluates to `NULL` to prevent division-by-zero errors. The UI displays `N/A` or `+100% (Gift)`.
- **Negative Value Floor:** `current_value_eur` is floored at `0.00` (`MAX(0, market_value - estimated_missing_cost)`). High part-replacement costs will never yield negative asset values for an instance.

## 2. Catalog & Inventory Lifecycle
- **Custom Builds & Unlisted Sets:** Custom builds/MOCs or uncataloged sets allow `set_number = NULL` and flag `is_custom = true`. External metadata auto-population is disabled for these items.
- **Multi-Instance Aggregation:** Each physical unit is tracked as an individual `LegoSetInstance` row with independent attributes (cost, condition, storage location). Aggregate counts (`owned_copies_count`) derive dynamically from in-scope instances (`is_deleted = false AND ownership_status IN (IN_COLLECTION, LISTED_FOR_SALE)`).
- **Ownership Lifecycle Transitions:** 
  - Transitioning `ownership_status` to `SOLD` mandates non-null values for both `sale_price_eur` and `sale_date`.
  - Reverting `ownership_status` away from `SOLD` back to `IN_COLLECTION` or `LISTED_FOR_SALE` nullifies both `sale_price_eur` and `sale_date`.
  - Inactive statuses (`SOLD`, `GIFTED_AWAY`, `DONATED`, `LOST_OR_DAMAGED`, `DISPOSED`) are excluded from net-worth metrics and unrealized performance KPIs, but remain fully accessible in historical views.
- **Cascade Delete Blockers (`LegoSetModel`):** Deleting a `LegoSetModel` is blocked if referenced by any instance where `is_deleted = false` (regardless of `ownership_status`). All associated instances must be soft-deleted or reassigned first to preserve historical valuation context.
- **Sealed & Incomplete Edge Combinations:** `build_state = SEALED` paired with `completeness_status = MISSING_PARTS` is permitted (e.g., documented factory packaging omissions). `current_value_eur` deducts `estimated_missing_cost_eur` regardless of build state.

## 3. Storage Hierarchy & Capacity Management
- **Storage Location Deletion Guard:** Soft-deleting a `StorageLocation` is hard-blocked while any active `LegoSetInstance` references it. Items must be reallocated to a different location or unassigned first.
- **Soft Capacity Warnings vs. Hard Blocking:** Assigning an instance to a location where `is_full = true` (`capacity_pct >= 100`) issues a UI warning but does not block save operations.
- **Manual Capacity Estimation:** `capacity_pct` is hand-annotated (0–100%) and independent of `stored_count`. Changing instances in a container does not recalculate `capacity_pct`.

## 4. Operational & Technical Integrity
- **Ownership Reconstruction via Audit Logging:** Historical ownership trends ("copies owned on date X") rely on `AuditLog` diffs for `ownership_status` and `is_deleted` field changes.
- **Stale Valuation Alerts:** If the latest valuation timestamp (`as_of_date`) exceeds the system threshold (e.g., 90 days), the UI displays a "Stale Valuation" indicator while preserving the existing calculated value.
- **Media Asset Handling:**
  - URL images store reference links only (no remote file scraping).
  - File uploads validate MIME types and magic bytes prior to persistence in Core `Document` storage.

## Additional / Enriched Requirements
- **Sealed vs built vs parts-out valuation** — three value types tracked separately per set model; the applicable one drives net worth based on each instance's `build_state`.
- **Barcode/box QR scan (future)** — scan the box barcode to resolve `set_number` for fast entry.
- **Instructions & minifig inventory (future)** — optional per-instance minifig checklist reusing the `MissingPart` pattern.
- **Storage capacity alerts (future)** — notify when a location nears or reaches `capacity_pct = 100`.

## Definition of Done
- [ ] `LegoSetModel` CRUD; find-or-create by `set_number`; soft-delete blocked while any non-deleted instance references it (regardless of ownership status).
- [ ] `LegoSetInstance` CRUD (minimal required: model reference + `acquisition_cost_eur`); soft-delete; no `quantity` field — one row per physical copy.
- [ ] `owned_copies_count` aggregation renders correctly per model (in-scope instances only).
- [ ]  metadata pre-fill never overwrites manual edits.
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