# 0026 — Carregar is an action, not a place

## Context

Uploading invoices had its own top-level tab in the Supermercado module. A tab
is a *place* — somewhere you navigate to and come back from — and uploading is
not a place: it is something you do while looking at your invoices, and want to
see the result of in the list you were already reading.

The cost was concrete. Reaching «Carregar» meant leaving «Faturas», losing its
filters and page position, and then navigating back to see whether anything had
arrived. The tab strip also carried twelve tabs, one of which was a verb.

## Decision

The «Carregar» tab is removed. Uploading is a **button on the invoice list** that
opens a modal containing the same drop zone and camera capture, plus the live
processing queue underneath it, so the outcome of the upload is visible without
navigating anywhere.

This changes global navigation, which is why it is recorded here: the URL
`?tab=carregar` no longer resolves to anything, and the module now has eleven
tabs, all of them nouns.

## Consequences

- The processing queue is rendered twice — compactly inside the modal, in full
  under «Processamento». It is one component with a `compact` flag, not a copy.
- The modal is where the parser-profile override lives, next to the files it
  applies to, rather than as a setting somewhere else.
- `status-panel`'s deep links were updated in the same change; nothing else
  referenced the removed tab.
- A future PWA share target ("share a receipt photo to FinManager") lands on the
  invoice list and opens this modal, rather than needing a route of its own.
