"""Merchant resolution — it runs **first**, because it selects the parser.

Priority is **printed NIF → alias → fuzzy name**. A receipt may carry two NIFs,
the merchant's and the household's, and the Portuguese numbering plan tells them
apart deterministically (Decision #29). A NIF that validates but matches no
merchant — or a *different* merchant than the name suggests — emits
``merchant_nif_mismatch`` and sends the receipt to review; it is never silently
overridden.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.core import Merchant
from app.services.supermarket.confidence import DecisionReason
from app.services.supermarket.normalize import normalize_merchant_name

AUTO_ACCEPT_SIMILARITY = 0.78
REVIEW_SIMILARITY = 0.70


@dataclass(slots=True)
class MerchantResolution:
    merchant_id: uuid.UUID | None
    score: Decimal
    reasons: list[DecisionReason]
    mismatch: bool = False


def _by_nif(db: DbSession, nif: str | None) -> Merchant | None:
    if not nif:
        return None
    return db.scalar(select(Merchant).where(Merchant.nif == nif, Merchant.is_deleted.is_(False)))


def best_name_match(db: DbSession, name: str | None) -> tuple[Merchant | None, float]:
    """Token-set ratio over canonical names *and* learned aliases."""
    if not name:
        return None, 0.0
    needle = normalize_merchant_name(name)
    best: Merchant | None = None
    best_score = 0.0
    for merchant in db.scalars(select(Merchant).where(Merchant.is_deleted.is_(False))).all():
        candidates = [merchant.name, *(str(a) for a in (merchant.aliases or []))]
        score = max(
            fuzz.token_set_ratio(needle, normalize_merchant_name(candidate)) / 100
            for candidate in candidates
        )
        if score > best_score:
            best, best_score = merchant, score
    return best, best_score


def resolve(
    db: DbSession,
    *,
    printed_nif: str | None,
    name_hint: str | None,
    profile_merchant_id: uuid.UUID | None,
) -> MerchantResolution:
    reasons: list[DecisionReason] = []

    by_nif = _by_nif(db, printed_nif)
    if printed_nif and by_nif is None:
        reasons.append(
            DecisionReason(
                "merchant_nif_unknown",
                f"NIF {printed_nif} válido mas sem comerciante correspondente.",
            )
        )
    if by_nif is not None:
        mismatch = profile_merchant_id is not None and profile_merchant_id != by_nif.id
        if mismatch:
            reasons.append(
                DecisionReason(
                    "merchant_nif_mismatch",
                    "O NIF impresso aponta para um comerciante diferente do perfil detetado.",
                )
            )
        reasons.append(
            DecisionReason(
                "merchant_by_nif", f"NIF {printed_nif} → {by_nif.name}", Decimal("1.000")
            )
        )
        return MerchantResolution(by_nif.id, Decimal("1.000"), reasons, mismatch=mismatch)

    if profile_merchant_id is not None:
        reasons.append(
            DecisionReason(
                "merchant_by_profile",
                "Comerciante do perfil de leitura detetado.",
                Decimal("0.900"),
            )
        )
        return MerchantResolution(profile_merchant_id, Decimal("0.900"), reasons)

    merchant, score = best_name_match(db, name_hint)
    rounded = Decimal(str(round(score, 3)))
    if merchant is not None and score >= AUTO_ACCEPT_SIMILARITY:
        reasons.append(
            DecisionReason("merchant_by_name", f"«{name_hint}» → {merchant.name}", rounded)
        )
        return MerchantResolution(merchant.id, rounded, reasons)
    if merchant is not None and score >= REVIEW_SIMILARITY:
        reasons.append(
            DecisionReason(
                "merchant_uncertain",
                f"«{name_hint}» parece {merchant.name} mas abaixo do limiar de aceitação.",
                rounded,
            )
        )
        return MerchantResolution(merchant.id, rounded, reasons)

    reasons.append(
        DecisionReason("merchant_unresolved", "Comerciante não identificado.", Decimal(0))
    )
    return MerchantResolution(None, Decimal(0), reasons)
