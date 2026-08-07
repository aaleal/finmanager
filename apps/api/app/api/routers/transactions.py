"""Ledger contract placeholder for the shared transaction picker (M9 UX-9.7).

The picker component is built now because M9 needs it; the ledger it queries
arrives with M2. Until then this endpoint answers honestly with an empty result
and ``ledger_available: false`` so the UI can explain itself instead of failing.
See docs/decisions/0005-defer-transaction-fk.md.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentAuth, Db

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionSuggestion(BaseModel):
    id: uuid.UUID
    booked_date: dt.date
    description: str
    amount_eur: Decimal
    account_label: str | None = None
    score: float


class SuggestionResponse(BaseModel):
    ledger_available: bool
    message: str | None = None
    items: list[TransactionSuggestion]


@router.get("/suggest", response_model=SuggestionResponse)
def suggest(
    ctx: CurrentAuth,
    db: Db,
    near_date: dt.date | None = None,
    amount_eur: Decimal | None = None,
    search: str | None = None,
    window_days: int = 3,
) -> SuggestionResponse:
    return SuggestionResponse(
        ledger_available=False,
        message=(
            "O livro-razão bancário chega com o módulo de Banca. "
            "Até lá, pode registar a compra sem ligação ao extrato."
        ),
        items=[],
    )
