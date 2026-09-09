"""FR-1.14 — reconciling a receipt to the bank statement that paid for it.

The ledger belongs to the Banking module and is **never redefined here**. Until it
exists this ships the contract and degrades honestly: candidate lookup answers
``ledger_available: false``, no `Link` is proposed, and the UI explains itself
rather than appearing broken. The same ship-the-contract-defer-the-FK posture as
docs/decisions/0005-defer-transaction-fk.md.

When the ledger lands, only ``candidates()`` changes: everything below already
scores, explains and writes the `Link` rows.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.core import Link
from app.models.supermarket import SupermarketReceipt

LINK_TYPE = "RECEIPT_TRANSACTION"
FROM_TYPE = "SupermarketReceipt"
TO_TYPE = "Transaction"

#: Configurable window and tolerance (FR-1.14).
DEFAULT_WINDOW_DAYS = 3
DEFAULT_AMOUNT_TOLERANCE = Decimal("0.02")
#: Above this a link is created as CONFIRMED; below it, a human decides.
AUTO_LINK_CUTOFF = Decimal("0.90")


@dataclass(frozen=True, slots=True)
class Candidate:
    transaction_id: uuid.UUID
    booked_date: dt.date
    amount_eur: Decimal
    description: str
    score: Decimal
    reasons: list[dict[str, Any]]


class LedgerProvider(Protocol):
    """Implemented for real by the Banking module."""

    available: bool

    def candidates(
        self,
        db: DbSession,
        *,
        entity_id: uuid.UUID,
        near_date: dt.date,
        amount_eur: Decimal,
        merchant_id: uuid.UUID | None,
        window_days: int,
        amount_tolerance: Decimal,
    ) -> list[Candidate]: ...


class AbsentLedger:
    """The honest placeholder: no ledger, therefore no candidates and no guesses."""

    available = False

    def candidates(
        self,
        db: DbSession,
        *,
        entity_id: uuid.UUID,
        near_date: dt.date,
        amount_eur: Decimal,
        merchant_id: uuid.UUID | None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        amount_tolerance: Decimal = DEFAULT_AMOUNT_TOLERANCE,
    ) -> list[Candidate]:
        return []


_provider: LedgerProvider = AbsentLedger()


def register_provider(provider: LedgerProvider) -> None:
    """The Banking module plugs the real ledger in here."""
    global _provider
    _provider = provider


def is_available() -> bool:
    return _provider.available


def propose_link(
    db: DbSession, receipt: SupermarketReceipt, *, actor_user_id: uuid.UUID | None = None
) -> Link | None:
    """Score the best candidate and either link it or route it to review."""
    if not _provider.available or receipt.purchase_date is None or receipt.total_eur <= 0:
        return None
    if existing_link(db, receipt.id) is not None:
        return None

    candidates = _provider.candidates(
        db,
        entity_id=receipt.entity_id,
        near_date=receipt.purchase_date,
        amount_eur=receipt.total_eur,
        merchant_id=receipt.merchant_id,
        window_days=DEFAULT_WINDOW_DAYS,
        amount_tolerance=DEFAULT_AMOUNT_TOLERANCE,
    )
    if not candidates:
        return None

    best = max(candidates, key=lambda candidate: candidate.score)
    link = Link(
        from_type=FROM_TYPE,
        from_id=receipt.id,
        to_type=TO_TYPE,
        to_id=best.transaction_id,
        link_type=LINK_TYPE,
        confidence=best.score,
        decision_reasons=best.reasons,
        status="CONFIRMED" if best.score >= AUTO_LINK_CUTOFF else "SUGGESTED",
        created_by=actor_user_id,
    )
    db.add(link)
    db.flush()
    return link


def existing_link(db: DbSession, receipt_id: uuid.UUID) -> Link | None:
    return db.scalar(
        select(Link).where(
            Link.from_type == FROM_TYPE,
            Link.from_id == receipt_id,
            Link.link_type == LINK_TYPE,
            Link.status != "DISMISSED",
        )
    )


def link_manually(
    db: DbSession,
    receipt: SupermarketReceipt,
    *,
    transaction_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
) -> Link:
    """What the shared transaction picker calls once a human has chosen."""
    link = existing_link(db, receipt.id)
    if link is not None:
        link.to_id = transaction_id
        link.status = "CONFIRMED"
        link.confidence = Decimal("1.000")
        link.decision_reasons = [
            {"rule": "manual_link", "detail": "Ligação escolhida à mão.", "score": "1.000"}
        ]
    else:
        link = Link(
            from_type=FROM_TYPE,
            from_id=receipt.id,
            to_type=TO_TYPE,
            to_id=transaction_id,
            link_type=LINK_TYPE,
            confidence=Decimal("1.000"),
            decision_reasons=[
                {"rule": "manual_link", "detail": "Ligação escolhida à mão.", "score": "1.000"}
            ],
            status="CONFIRMED",
            created_by=actor_user_id,
        )
        db.add(link)
    db.flush()
    return link


def unlink(db: DbSession, receipt_id: uuid.UUID) -> None:
    link = existing_link(db, receipt_id)
    if link is not None:
        link.status = "DISMISSED"
        db.flush()
