# 0017 — The fiscal QR is the highest-confidence anchor

## Context

FR-1.6. Portaria 195/2020 mandates a QR code on every Portuguese fiscal document
encoding issuer NIF, buyer NIF, document type, date, a unique document id, the
ATCUD, the VAT breakdown per rate and the gross total — but **no line items**.

## Decision

Decode the QR with `pyzbar` when it is readable and let it override the parsed
date and gross total (`pipeline.run`, guarded by `anchor.has_qr`); fall back to
the ATCUD printed as plain text otherwise. `atcud_valid` / `atcud_reason` are
recorded either way. A missing or malformed QR lowers confidence and flags the
receipt for review, but it never blocks ingestion — the ATCUD is also printed as
plain text on every fixture we have, so a QR that will not decode still yields a
reference value.

Duplicates are then **prevented, not detected**: `UNIQUE (entity_id,
atcud_code)` (partial, `atcud_code IS NOT NULL AND is_deleted = false`) plus
SHA-256 document idempotency on upload.

## Consequences

- Measured: the QR decoded on all ten digital PDFs, so merchant resolution on
  every one of them was exact (an organisational NIF match) rather than fuzzy
  (`rapidfuzz` name matching, reserved for when the QR or a printed NIF is
  unavailable).
- `pyzbar` needs the OS package `libzbar0`. Its absence degrades to the printed
  ATCUD rather than failing the parse — the same "local ships enabled, stays
  local without a dependency" posture as every other stage.
- IVA is **not** modelled anywhere in this module: the printed class token is
  kept verbatim in `iva_class_raw` and read by nothing. Consistently, the QR's
  VAT breakdown is stored whole in `raw_ocr_payload` and never decomposed into
  per-rate columns — decomposing one source of VAT data and not the other would
  be worse than decomposing neither.
