"""Product resolution and the learning loop.

**There is no exact key.** Real *talões* print neither an EAN nor an article
code, only a truncated description (Decision #23), so resolution is
normalize-then-match:

    learned ``ProductAlias`` on ``description_norm``
        -> normalized fuzzy match >= 0.78 (review band 0.70-0.78)
        -> a brand-new product

Learning happens on the **first** confirmed correction: ``confidence`` starts low
and rises with ``correction_count``. Waiting for five corrections would discard
exactly the signal that makes matching improve (Decision #5).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.products import MasterProduct, ProductAlias
from app.models.supermarket import SupermarketReceiptItem
from app.services.supermarket.normalize import normalize_description

AUTO_ACCEPT = 0.78
REVIEW_BAND = 0.70

#: Learned trust starts deliberately low and climbs with confirmations.
_ALIAS_CONFIDENCE = {0: Decimal("0.600"), 1: Decimal("0.850"), 2: Decimal("0.950")}
_ALIAS_CONFIDENCE_MAX = Decimal("0.990")


@dataclass(slots=True)
class Match:
    master_product_id: uuid.UUID | None
    score: Decimal
    reasons: list[dict[str, Any]]


def _reason(rule: str, detail: str, score: Decimal | None = None) -> dict[str, Any]:
    return {"rule": rule, "detail": detail, "score": None if score is None else str(score)}


def alias_confidence(correction_count: int) -> Decimal:
    return _ALIAS_CONFIDENCE.get(correction_count, _ALIAS_CONFIDENCE_MAX)


def _combined(left: str, right: str) -> float:
    """Token-set forgiveness tempered by token-sort strictness.

    ``token_set_ratio`` alone returns 100 whenever one token set contains the
    other, which makes every short catalogue name a magnet for longer receipt
    lines. Averaging in ``token_sort_ratio``, which counts the words that are
    *missing*, separates «POLPA TOMATE GULOSO 500G» → «Polpa de Tomate Guloso
    500g» (97) from → «Tomate» (70).
    """
    return (fuzz.token_set_ratio(left, right) + fuzz.token_sort_ratio(left, right)) / 2


def _candidates(db: DbSession) -> list[tuple[str, uuid.UUID]]:
    """Every name the catalogue answers to: canonical names and learned aliases."""
    products = db.execute(
        select(MasterProduct.id, MasterProduct.canonical_name, MasterProduct.brand).where(
            MasterProduct.is_deleted.is_(False)
        )
    ).all()
    names: list[tuple[str, uuid.UUID]] = []
    for product_id, canonical_name, brand in products:
        names.append((normalize_description(canonical_name), product_id))
        if brand:
            names.append((normalize_description(f"{canonical_name} {brand}"), product_id))

    aliases = db.execute(
        select(ProductAlias.description_norm, ProductAlias.master_product_id)
    ).all()
    names.extend((row[0], row[1]) for row in aliases)
    return names


def resolve_description(
    db: DbSession, *, merchant_id: uuid.UUID | None, description_norm: str
) -> Match:
    if not description_norm:
        return Match(None, Decimal("0.000"), [_reason("empty_description", "Linha sem texto.")])

    if merchant_id is not None:
        alias = db.scalar(
            select(ProductAlias).where(
                ProductAlias.merchant_id == merchant_id,
                ProductAlias.description_norm == description_norm,
            )
        )
        if alias is not None:
            alias.last_used_at = dt.datetime.now(dt.UTC)
            return Match(
                alias.master_product_id,
                Decimal(alias.confidence),
                [
                    _reason(
                        "product_alias",
                        "Correspondência aprendida para este comerciante.",
                        Decimal(alias.confidence),
                    )
                ],
            )

    candidates = _candidates(db)
    if not candidates:
        # Decision #39: nothing resolves, and that is correct. The fix is data.
        return Match(
            None, Decimal("0.000"), [_reason("empty_catalogue", "Catálogo de produtos vazio.")]
        )

    lookup = dict(candidates)
    # Shortlist with `token_set_ratio` (fast, and forgiving of word order), then
    # re-rank. On its own it scores a *subset* at a flat 100, so «POLPA TOMATE
    # GULOSO 500G» would resolve to a product merely called «Tomate»;
    # `token_sort_ratio` is what notices the missing words.
    shortlist = process.extract(
        description_norm, list(lookup), scorer=fuzz.token_set_ratio, limit=25
    )
    if not shortlist:
        return Match(None, Decimal("0.000"), [_reason("no_match", "Sem correspondência.")])

    name, raw_score = max(
        ((candidate, _combined(description_norm, candidate)) for candidate, _, _ in shortlist),
        key=lambda pair: pair[1],
    )
    score = Decimal(str(round(raw_score / 100, 3)))
    if score >= Decimal(str(AUTO_ACCEPT)):
        return Match(lookup[name], score, [_reason("product_fuzzy", f"«{name}»", score)])
    if score >= Decimal(str(REVIEW_BAND)):
        return Match(
            None,
            score,
            [_reason("product_uncertain", f"Parece «{name}» mas abaixo do limiar.", score)],
        )
    return Match(
        None,
        score,
        [_reason("product_unresolved", "Nenhum produto suficientemente próximo.", score)],
    )


class CatalogueResolver:
    """The ``ProductResolver`` the pipeline plugs in (M1a's seam)."""

    def resolve(
        self, db: DbSession, *, merchant_id: uuid.UUID | None, item: SupermarketReceiptItem
    ) -> tuple[uuid.UUID | None, Decimal | None, list[dict[str, Any]]]:
        match = resolve_description(
            db, merchant_id=merchant_id, description_norm=item.description_norm
        )
        return match.master_product_id, match.score, match.reasons


def learn(
    db: DbSession,
    *,
    master_product_id: uuid.UUID,
    merchant_id: uuid.UUID,
    merchant_description: str,
) -> ProductAlias:
    """Record a human's correction so the same line resolves itself next time."""
    description_norm = normalize_description(merchant_description)[:300]
    alias = db.scalar(
        select(ProductAlias).where(
            ProductAlias.merchant_id == merchant_id,
            ProductAlias.description_norm == description_norm,
        )
    )
    if alias is None:
        alias = ProductAlias(
            master_product_id=master_product_id,
            merchant_id=merchant_id,
            merchant_description=merchant_description[:300],
            description_norm=description_norm,
            correction_count=0,
            confidence=alias_confidence(0),
        )
        db.add(alias)
    else:
        # A correction that *changes* the target restarts the trust it had earned.
        if alias.master_product_id != master_product_id:
            alias.master_product_id = master_product_id
            alias.correction_count = 0
        alias.merchant_description = merchant_description[:300]

    alias.correction_count += 1
    alias.confidence = alias_confidence(alias.correction_count)
    alias.last_used_at = dt.datetime.now(dt.UTC)
    db.flush()
    return alias
