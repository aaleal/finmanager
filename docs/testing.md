# Testing

## The rule

**Coverage is not a goal.** Tests exist only for the few things that are genuinely
load-bearing and easy to get subtly wrong. Everything else is validated by
exploratory verification against the module's Definition of Done. Hand-written
exhaustive CRUD tests are explicitly not wanted — they cost more than they protect.

Every test file's header states **which rubric bullet or gotcha it protects
against**, so the output of `make check` doubles as a rubric checklist.

## Running

```bash
make check        # lint + types + tests, both apps — the only gate
make test-api     # backend only
make test-web     # frontend only
```

Everything runs inside containers. Integration tests create and drop a dedicated
`finmanager_test` database on the same Postgres container; they never touch the
development data.

## What is covered today

### Backend — `apps/api/tests/`

| File | Protects |
|---|---|
| `unit/test_money_decimal.py` | «no float money anywhere» — floats are rejected at the boundary, rounding is half-up to cents, repeated addition stays exact |
| `unit/test_lego_roi.py` | M9 unrealized ROI math: positive, negative, **gift (cost 0 → `None`)**, **no value set (→ `None`)**, and both at once |
| `unit/test_lego_storage_capacity.py` | M9 storage capacity math and the rule that `capacity_pct` is a human estimate, never derived from `stored_count` |
| `unit/test_receipt_fs_split.py` | An Fs article is appended and leaves every printed figure byte-identical — even on a `CONFIRMED` receipt |
| `unit/test_receipt_price_arithmetic.py` | Only `pvp − promo − invoice_allocated` reconciles, and the invoice-level discount is prorated (largest-remainder), never a per-item promo |
| `unit/test_receipt_confidence.py` | The confidence engine is pure — identical input yields byte-identical `(status, confidence, decision_reasons)` |
| `unit/test_receipt_parsers.py` | All four merchant profiles parse their own fixtures correctly, including their opposite discount semantics, and the Piquete photograph parses end to end through OCR |
| `unit/test_receipt_normalization.py` | Protects the brief §3 rule — normalize Portuguese product text before rapidfuzz token-set ratio; match threshold ~0.78, review band ~0.70–0.78 — and the rubric bullet that every line resolves to a `MasterProduct`: accent/case/punctuation stripping, size tokens surviving, multipack weight (`3X250ML` is 0,750 kg, not 0,250), pt-PT decimal parsing including parenthesised negatives, merchant name folding, unit-token mapping (`KIL` and `KG` on one Piquete talão), and alias confidence climbing with each confirmation |
| `integration/test_lego_lifecycle.py` | Ownership transitions, KPI exclusion of `SOLD`/`GIFTED`, sale fields cleared on return, delete guards (model with live copies, location with assigned copies), find-or-create by set number, `value_updated_at` stamping, and that every mutation writes an `AuditLog` row |
| `integration/test_household_rbac.py` | VIEWER is read-only, OWNER gate, «todas» refuses to guess an owner, read-only entities refuse writes, and the **last-OWNER safeguard** |
| `integration/test_document_security.py` | Magic-byte validation beats the supplied filename, disguised executables are refused, files land outside any web root, deduplication by hash, and signed URLs that fail closed on tamper or expiry |
| `integration/test_receipt_ingestion.py` | The M1a exit criterion — a Continente PDF and a Lidl PDF upload, parse, reconcile to their printed totals, and confirm — plus idempotent re-import, ATCUD duplicate prevention and the receipt status machine. Rewritten for M1b: now that the catalogue stage runs, an empty catalogue scores `product_match = 0` and the same clean PDF goes to review instead of auto-accepting — exactly what [ADR-0018](decisions/0018-a-stage-that-did-not-run-is-not-a-stage-that-failed.md) predicted |
| `integration/test_receipt_catalogue.py` | The M1b rubric bullets *«every line resolves to a `MasterProduct` and inherits its category»*, *«a brand-new product arrives with an `AUTO` suggestion a human can promote to `VALIDATED` once, for every past and future line»*, and the four category-governance rules (rename, reparent, merge, retire) |
| `integration/test_receipt_legacy_import.py` | The M1b exit criterion — the 2025 import yields the measured product and reconciliation counts on the real sheet, a re-parse of the fixtures now resolves products and categories, and a correction sticks |
| `integration/test_receipt_price_history.py` | The M1c exit criterion, 14 tests: observations are frozen on confirm; recording twice writes nothing; a correction appends and never rewrites; an Fs observation carries the notional value in **both** price columns and never `0.00`; €/kg trends across merchants; the `fs` filter redraws the series; a missing weight leaves €/kg `NULL`; last known price pre-fills manual entry; shrinkflation fires on a seeded 250 g → 200 g case at the same price (`margin_signal = −0.2000`); a stable pack fires nothing; fewer than three priors fires nothing; an Fs article moves the notional measure and nothing else; loyalty is a `GROUP BY`; the ledger link degrades honestly. Also covers a pack-variant case: a 500 g and a 1 kg bag of one product yield directly comparable €/kg (13,96 and 13,60), with the weight read from the size token in the description |
| `integration/test_receipt_provider_seams.py` | Protects the rubric bullets *«the full pipeline completes with egress blocked, at default settings»* and *«the provider seam is exercised by a fake remote engine, proving a stage can be swapped without touching the pipeline»*: monkeypatches `socket.socket.connect` to raise on anything other than Postgres and Redis, then parses a real Continente PDF end to end; registers a `FakeRemoteResolver` through `pipeline.register_product_resolver()` and asserts every line resolves through it, and that passing `None` reports `product_match_unavailable` rather than scoring a failure |
| `integration/test_receipt_api_surface.py` | Protects the Module 1 HTTP surface — see below |

### Golden extraction fixtures

`apps/api/tests/fixtures/golden/` pins the **extraction** stage, not the parse:
 one committed JSON of word boxes (`engine`, `document_kind`, per-page `lines`)
per real *talão* under `apps/api/tests/fixtures/receipts/` — four Continente,
four Pingo Doce, two Lidl PDFs and the one Piquete photograph. With the word
boxes committed, a parser change shows up as a diff in parsed output alone, and
an extractor upgrade (a `pdfplumber`/`pytesseract` version bump, say) shows up
as a diff in these files — the two failure modes can never masquerade as each
other. Regenerate them after a deliberate extraction change with:

```bash
docker compose run --rm --no-deps api python -m tests.fixtures.regenerate_golden
```

### Why an HTTP-surface test, when service tests already cover the rules

Every other M1 test drives services directly, which is where the domain rules live —
but that also means a router that serialises a response wrongly still passes them
all. `test_receipt_api_surface.py` walks the whole surface through the real app
instead: authenticated, CSRF-checked, asserting a usable status on every route. It
exists because it caught a real bug — `PricePoint` and `ShrinkflationSignal` are
`@dataclass(slots=True)` and have no `__dict__`, so
`/api/receipts/analytics/shrinkflation` returned a 500 that no service-level test
could see. Its fixture also clears the Redis rate-limit counters, because
`/api/setup` is rate-limited per client IP and every test in the file calls it —
without the reset, later tests in the file would fail against the limiter rather
than the route under test.

### The legacy import fixture

`apps/api/tests/fixtures/SUPERMARKET_2025.xlsx` is the real 2,429-row household
sheet, committed rather than synthesised, because a synthetic sheet cannot
prove the timestamp-snap window or the largest-remainder residual actually
reconcile a household's years of hand-kept data. `test_receipt_legacy_import.py`
is the slowest file in the tree — roughly 100 s — because it imports that sheet
several times over (whole sheet, grocery-only, and a re-run to prove
idempotency). That cost is deliberate: it is the only test that proves the
numbers in [ADR-0021](decisions/0021-the-legacy-sheet-is-validated-not-trusted.md),
rather than asserting against a fixture built to already agree with the code.

### Frontend — co-located `*.test.ts(x)`

| File | Protects |
|---|---|
| `src/lib/format.test.ts` | pt-PT EUR formatting through the single money util; em dash (never `0 %`) for a null ROI; pt-PT date and thousands separators |
| `src/features/lego/constants.test.ts` | M9 FR-9.10 — marketplace links are built from a `set_number` template, nothing stored or fetched |

## Conventions

- `tests/unit/` holds pure domain logic with **no I/O**. If a test needs a database
  it belongs in `tests/integration/` and carries `pytest.mark.integration`.
- One file per concern, named after what it protects (`test_lego_roi.py`), not after
  the module it happens to import.
- Fixtures live in `tests/conftest.py`: `db`, `household`, `owner`, `entity` and an
  `api_client` that overrides the request-scoped session.
- Frontend tests sit next to the code they cover; end-to-end coverage is reserved for
  the crown-jewel flows once those modules exist (receipt review, review-queue
  confirm).
- **Playwright e2e tooling is still not set up.** M1 is complete across all three
  slices (M1a/M1b/M1c) and records this as a deliberate deferral rather than
  claiming coverage it does not have. «Carregar → rever → confirmar» remains the
  first candidate flow once the tooling lands.

## Adding a test

Ask: *if this were silently wrong, would money, history or a lifecycle guard be
wrong?* If not, do not write the test. If yes, write it, and start the file with a
docstring naming the rubric bullet it defends.

**Playwright e2e tooling is still not set up.** This remains a deliberate
deferral, not an oversight, across every M1 slice: nothing above substitutes for
it, and «Carregar → rever → confirmar» is still the first candidate flow once the
tooling lands.
