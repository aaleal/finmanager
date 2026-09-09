"""The confidence engine — pure, deterministic, and the only place a status is decided.

No clock reads, no randomness, no I/O: identical input yields byte-identical
``(status, confidence, decision_reasons)`` across runs, which is what makes a
quality change traceable to the switch that caused it rather than to luck.

Learned corrections live in ``ProductAlias``, deliberately **outside** this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

Status = Literal["AUTO_ACCEPTED", "NEEDS_REVIEW"]

SCORE_PLACES = Decimal("0.001")

#: Suggested starting weights (orchestrator §3 Ingestion).
WEIGHTS: dict[str, Decimal] = {
    "product_match": Decimal("0.30"),
    "ocr_text": Decimal("0.25"),
    "arithmetic": Decimal("0.25"),
    "merchant_match": Decimal("0.20"),
}

DEFAULT_AUTO_ACCEPT = Decimal("0.90")
DEFAULT_REVIEW = Decimal("0.60")


@dataclass(frozen=True, slots=True)
class DecisionReason:
    rule: str
    detail: str
    score: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "detail": self.detail,
            "score": None if self.score is None else str(self.score),
        }


@dataclass(frozen=True, slots=True)
class ReceiptSignals:
    """Everything the engine is allowed to look at.

    A signal of ``None`` means *the stage did not run* — its weight is
    redistributed over the stages that did, and the omission is recorded as a
    reason. A signal of ``0`` means *the stage ran and found nothing*, which is a
    genuine failure and is scored as one.
    """

    merchant_match: Decimal | None = None
    ocr_text: Decimal | None = None
    arithmetic_matches: bool | None = None
    product_match: Decimal | None = None
    #: Reasons gathered upstream (parser choice, ATCUD, engine names) that ride
    #: along into the stored explanation without affecting the score.
    context: list[DecisionReason] = field(default_factory=list)
    #: Set when a receipt must never be auto-accepted regardless of its score —
    #: a hand-written slip, or a photograph the household asked to always review.
    force_review: str | None = None


def _clamp(value: Decimal) -> Decimal:
    return max(Decimal(0), min(Decimal(1), Decimal(value)))


def score(
    signals: ReceiptSignals,
    *,
    auto_accept_threshold: Decimal = DEFAULT_AUTO_ACCEPT,
    review_threshold: Decimal = DEFAULT_REVIEW,
) -> tuple[Status, Decimal, list[dict[str, Any]]]:
    """Combine the signals into one ``[0,1]`` score and a status.

    Arithmetic reconciliation is a *signal*, not a gate: a mismatch **halves** the
    score and emits ``arithmetic_mismatch``. It never silently discards a receipt.
    """
    reasons: list[DecisionReason] = list(signals.context)

    contributions: dict[str, Decimal] = {}
    for name, raw in (
        ("merchant_match", signals.merchant_match),
        ("ocr_text", signals.ocr_text),
        ("product_match", signals.product_match),
    ):
        if raw is None:
            reasons.append(
                DecisionReason(f"{name}_unavailable", "Fase não executada; peso redistribuído.")
            )
            continue
        contributions[name] = _clamp(raw)

    if signals.arithmetic_matches is None:
        reasons.append(
            DecisionReason("arithmetic_unavailable", "Sem total impresso para reconciliar.")
        )
    else:
        contributions["arithmetic"] = Decimal(1) if signals.arithmetic_matches else Decimal(0)

    weight_total = sum((WEIGHTS[name] for name in contributions), Decimal(0))
    if weight_total == 0:
        reasons.append(DecisionReason("no_signals", "Nenhum sinal disponível.", Decimal(0)))
        return "NEEDS_REVIEW", Decimal("0.000"), [r.as_dict() for r in reasons]

    combined = Decimal(0)
    for name, value in contributions.items():
        weighted = WEIGHTS[name] * value / weight_total
        combined += weighted
        reasons.append(
            DecisionReason(
                name, f"sinal {value.quantize(SCORE_PLACES)}", weighted.quantize(SCORE_PLACES)
            )
        )

    if signals.arithmetic_matches is False:
        combined = combined / 2
        reasons.append(
            DecisionReason(
                "arithmetic_mismatch",
                "A soma das linhas não bate certo com o total impresso; "
                "confiança reduzida a metade.",
                Decimal("-0.500"),
            )
        )

    confidence = _clamp(combined).quantize(SCORE_PLACES, rounding=ROUND_HALF_UP)

    if signals.force_review:
        reasons.append(DecisionReason("force_review", signals.force_review))
        return "NEEDS_REVIEW", confidence, [r.as_dict() for r in reasons]

    if confidence >= Decimal(auto_accept_threshold):
        status: Status = "AUTO_ACCEPTED"
    else:
        status = "NEEDS_REVIEW"
        reasons.append(
            DecisionReason(
                "below_auto_accept",
                f"{confidence} < {Decimal(auto_accept_threshold)}",
                confidence,
            )
        )
        if confidence < Decimal(review_threshold):
            reasons.append(
                DecisionReason("low_confidence", f"{confidence} < {Decimal(review_threshold)}")
            )

    return status, confidence, [r.as_dict() for r in reasons]


def item_confidence(
    *,
    text_quality: Decimal,
    has_price: bool,
    product_match: Decimal | None,
) -> tuple[Decimal, list[dict[str, Any]]]:
    """Per-line score, so every line carries a visible confidence of its own."""
    reasons = [
        DecisionReason(
            "ocr_text", "qualidade do texto", _clamp(text_quality).quantize(SCORE_PLACES)
        )
    ]
    value = _clamp(text_quality)
    if not has_price:
        value = value / 2
        reasons.append(DecisionReason("missing_price", "Linha sem valor legível."))
    if product_match is None:
        reasons.append(DecisionReason("product_match_unavailable", "Sem catálogo de produtos."))
    else:
        matched = _clamp(product_match)
        value = (value + matched) / 2
        reasons.append(
            DecisionReason(
                "product_match", "correspondência de produto", matched.quantize(SCORE_PLACES)
            )
        )
    return value.quantize(SCORE_PLACES, rounding=ROUND_HALF_UP), [r.as_dict() for r in reasons]
