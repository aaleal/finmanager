# 0019 — The product catalogue is shared, not entity-scoped

## Context

The module brief opens by saying every row carries `entity_id`, but the
`MasterProduct` attribute table it defines lists none. Both readings are
defensible until you ask what a product *is*: a tin of tomatoes does not become
a different tin because a different household member paid for it.

## Decision

`master_products` and `product_aliases` are household-level reference data,
exactly like `Merchant` and `Category`. Receipts and receipt lines stay
entity-scoped, as they always were.

## Consequences

- A product is the same product whoever bought it. A per-entity catalogue
  would fork the same coffee three ways and split every €/kg trend — and every
  learned alias — with it.
- Attribution is still complete: it lives on `Receipt.entity_id` and
  `ReceiptItem.entity_id`, not on the product.
- The trade is that one member renaming a product renames it for everyone.
  That is the same trade the household already accepted for merchants and
  categories, and, like those, it is audited.
