# 0025 — One Review Queue, deep-linked into the module that can resolve it

## Context

Two screens looked like review backlogs: the global «Fila de revisão»
(`/revisao`) and the Supermercado module's own «Fila» tab. That is precisely the
duplication the reuse protocol (orchestrator §5a rule 2) calls a defect — *"a
second review queue is a defect, not progress"*.

Inspection showed the duplication was half real:

- `/revisao` was still the Phase-0 **shell**. It listed `ReviewTask` rows, but
  its Confirm/Corrigir/Descartar buttons had no handlers, the reasons rendered as
  `JSON.stringify`, and there was no way to reach the subject.
- The module's «Fila» was never a review queue at all: it is the **processing**
  queue of UX-1.1, one row per `ProcessingJob`, with the parser profile that ran
  and *retry from the stored document*. Only its name collided.

## Decision

**There is exactly one Review Queue**, and it is a shared component
(`components/review-queue.tsx`) that the `/revisao` route renders as a thin
frame. It is generic over `{subject_type, subject_id, module, confidence,
suggested_payload, decision_reasons}` and resolves tasks through
`POST /review/tasks/{id}/resolve`.

It does **not** inline-edit a subject. Instead a `SUBJECT_ROUTES` table maps a
subject type to the screen that owns it, and «Abrir no módulo» navigates there —
`Receipt` opens at `/supermercado?tab=faturas&receipt=<id>`, which is the review
split pane, beside the original document.

The module's queue keeps its job and loses its ambiguous name: the tab is now
«Processamento», and the component says in its own docstring that it is not a
review queue.

## Consequences

- "Corrigir" as a generic inline editor was dropped rather than built. A receipt
  is corrected against its scanned original with running totals and an Fs split;
  reproducing a worse version of that inside a queue card would have been the
  second surface all over again. Confirm and Dismiss stay generic because they
  genuinely are.
- The review pane is now addressed by a URL parameter instead of component
  state. That is what makes the deep link possible, and it also makes any open
  invoice bookmarkable and shareable — the rule the brief already sets for
  filter state.
- Every future ingestion module (M2–M5) gets the queue *and* the hand-off for
  free by adding one line to `SUBJECT_ROUTES`.
- A module may embed the same component filtered to itself (`<ReviewQueue
  module="receipts" />`) if that ever helps. That is still one queue, rendered
  twice — not two.
