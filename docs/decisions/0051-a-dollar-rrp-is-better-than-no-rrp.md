# 0051 — A dollar RRP, assumed 1:1 as euros, is better than no RRP at all

## Context

[ADR-0039](0039-the-sets-own-fields-not-a-shops.md) restricted `rrp_eur` to
`LEGOCom.DE` only, on the grounds that importing a pound or dollar figure into
a column the whole application reads as euros would be worse than leaving it
empty.

In practice this leaves many older/retired sets with an empty PVP: LEGO
frequently stops selling a set on LEGO.com long before that store's German
listing (or never lists it there at all), so `LEGOCom.DE` is absent for a
large share of a real household's older collection, even when `LEGOCom.US`
still has a price on record.

An empty PVP is not actually the safer default here — a household comparing
its collection's cost/ROI wants a number to anchor to, and a dollar figure is
a much closer approximation of what a euro set cost than nothing at all,
especially since EUR/USD has stayed close to parity for most of this period.

## Decision

`rrp_eur` now reads `LEGOCom.DE` first and, only when Germany has no price,
falls back to `LEGOCom.US` — treated as euros with **no currency
conversion** (1:1). Any other store (e.g. `UK`) is still never used: this is
a narrow, explicit fallback, not a reopening of the "first store present"
chain ADR-0039 removed.

This only changes the exact value read from Brickset — nothing about how
`rrp_eur` is stored, displayed, or used downstream (ROI math, exports, ...)
changes.
